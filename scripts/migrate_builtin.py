"""
Migration script using only built-in Python modules (urllib + sqlite3).
No pip install required. Reads local SQLite, writes to Turso via HTTP API.
"""
import sqlite3
import json
import urllib.request
import urllib.error
import sys
import os
import time

# Turso credentials
DATABASE_URL = "libsql://inventory-hshaquib007.aws-ap-south-1.turso.io"
AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODg1MzU1NDYsImlkIjoiMDFhMDZkMDMtOWEwMS03NDY3LWFkMTgtZTRiZWI5YjFiMjYxIiwia2lkIjoib1llTExYZXBuaFA3SGhwMjZXODdyWWRENjRGdGFqb2hWZGxtUTR6bXpKUSIsInJpZCI6IjRkNTFlOWM4LTNjYTUtNDYxNy04ZTFlLWFkNzYwN2FiNzdiYSJ9.HAJ5hLLCyAhq4Xu3A3xnin2uZhoNg-zSF5crC11rpKQx9zbzQnVKqv65TJb5mxWcKwSPi-RlTEYYikvwzpEAAA"

# Convert libsql:// to https:// for the HTTP API
HOST = DATABASE_URL.replace("libsql://", "https://")

# Tables in order
TABLES = [
    'item_master',
    'job_master',
    'bom',
    'bom_lines',
    'grn',
    'grn_lines',
    'prn',
    'prn_lines',
    'pmi',
    'pmi_lines',
]

DDL = {
    'item_master': """CREATE TABLE IF NOT EXISTS item_master (
        id INTEGER PRIMARY KEY,
        item_code TEXT UNIQUE NOT NULL,
        product_code TEXT NOT NULL,
        item_name TEXT NOT NULL,
        uom TEXT NOT NULL,
        opening_stock REAL DEFAULT 0.0,
        grn_qty REAL DEFAULT 0.0,
        issued_qty REAL DEFAULT 0.0,
        "group" TEXT,
        sub_group TEXT,
        created_at TEXT,
        updated_at TEXT
    )""",
    'job_master': """CREATE TABLE IF NOT EXISTS job_master (
        id INTEGER PRIMARY KEY,
        job_no TEXT UNIQUE NOT NULL,
        job_detail TEXT NOT NULL,
        customer TEXT NOT NULL,
        job_group TEXT,
        created_at TEXT,
        updated_at TEXT
    )""",
    'bom': """CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY,
        bom_no TEXT NOT NULL,
        job_no TEXT NOT NULL,
        job_group TEXT,
        date TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT
    )""",
    'bom_lines': """CREATE TABLE IF NOT EXISTS bom_lines (
        id INTEGER PRIMARY KEY,
        bom_id INTEGER NOT NULL,
        bom_sr_no TEXT,
        job_no TEXT,
        item_code TEXT NOT NULL,
        product_code TEXT NOT NULL,
        item_name TEXT NOT NULL,
        uom TEXT NOT NULL,
        quantity REAL NOT NULL,
        "group" TEXT,
        sub_group TEXT,
        revision TEXT DEFAULT '0',
        baseline_item_name TEXT,
        baseline_quantity REAL,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (bom_id) REFERENCES bom(id)
    )""",
    'grn': """CREATE TABLE IF NOT EXISTS grn (
        id INTEGER PRIMARY KEY,
        grn_no TEXT UNIQUE NOT NULL,
        grn_date TEXT NOT NULL,
        supplier_name TEXT,
        invoice_no TEXT,
        invoice_date TEXT,
        job_group TEXT,
        remarks TEXT,
        created_at TEXT,
        updated_at TEXT
    )""",
    'grn_lines': """CREATE TABLE IF NOT EXISTS grn_lines (
        id INTEGER PRIMARY KEY,
        grn_id INTEGER NOT NULL,
        item_code TEXT NOT NULL,
        product_code TEXT NOT NULL,
        item_name TEXT NOT NULL,
        uom TEXT NOT NULL,
        received_qty REAL NOT NULL,
        date TEXT NOT NULL,
        po_number TEXT,
        job_no TEXT,
        last_purchase_price REAL DEFAULT 0.0,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (grn_id) REFERENCES grn(id)
    )""",
    'prn': """CREATE TABLE IF NOT EXISTS prn (
        id INTEGER PRIMARY KEY,
        prn_no TEXT UNIQUE NOT NULL,
        prn_date TEXT NOT NULL,
        job_no TEXT NOT NULL,
        job_group TEXT,
        status TEXT DEFAULT 'Pending',
        remarks TEXT,
        created_at TEXT,
        updated_at TEXT
    )""",
    'prn_lines': """CREATE TABLE IF NOT EXISTS prn_lines (
        id INTEGER PRIMARY KEY,
        prn_id INTEGER NOT NULL,
        bom_no TEXT,
        bom_sr_no TEXT,
        item_code TEXT NOT NULL,
        product_code TEXT NOT NULL,
        item_name TEXT NOT NULL,
        uom TEXT NOT NULL,
        job_no TEXT,
        required_qty REAL NOT NULL,
        prn_qty REAL NOT NULL,
        reserved_qty REAL DEFAULT 0.0,
        stock_qty REAL DEFAULT 0.0,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (prn_id) REFERENCES prn(id)
    )""",
    'pmi': """CREATE TABLE IF NOT EXISTS pmi (
        id INTEGER PRIMARY KEY,
        pmi_no TEXT UNIQUE NOT NULL,
        pmi_date TEXT NOT NULL,
        supplier_name TEXT,
        invoice_no TEXT,
        invoice_date TEXT,
        job_group TEXT,
        remarks TEXT,
        created_at TEXT,
        updated_at TEXT
    )""",
    'pmi_lines': """CREATE TABLE IF NOT EXISTS pmi_lines (
        id INTEGER PRIMARY KEY,
        pmi_id INTEGER NOT NULL,
        item_code TEXT NOT NULL,
        product_code TEXT NOT NULL,
        item_name TEXT NOT NULL,
        uom TEXT NOT NULL,
        received_qty REAL NOT NULL,
        date TEXT NOT NULL,
        job_no TEXT,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (pmi_id) REFERENCES pmi(id)
    )""",
}


def execute_sql(sql, params=None, retries=3):
    """Execute SQL on Turso via HTTP API with retry."""
    url = f"{HOST}/v2/pipeline"
    batch = [{"type": "execute", "stmt": {"sql": sql}}]
    if params:
        batch[0]["stmt"]["args"] = [
            {"type": "text", "value": str(v) if v is not None else None}
            for v in params
        ]

    payload = json.dumps({"requests": batch}).encode("utf-8")
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {AUTH_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt+1} after error: {e}")
                time.sleep(2)
            else:
                raise
    raise Exception("Max retries exceeded")


def execute_batch(sql, params_list, batch_size=10):
    """Execute a SQL statement with multiple parameter sets using pipeline batches."""
    url = f"{HOST}/v2/pipeline"
    total = len(params_list)
    inserted = 0

    for i in range(0, total, batch_size):
        chunk = params_list[i:i + batch_size]
        batch = []
        for params in chunk:
            batch.append({
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": [
                        {"type": "text", "value": str(v) if v is not None else None}
                        for v in params
                    ],
                },
            })

        payload = json.dumps({"requests": batch}).encode("utf-8")
        for attempt in range(3):
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {AUTH_TOKEN}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    for r in result.get("results", []):
                        if "error" in r:
                            print(f"  Error: {r['error']}")
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < 2:
                    print(f"  Retry {attempt+1}...")
                    time.sleep(3)
                else:
                    # Fall back to one-by-one
                    print(f"  Batch failed, trying one-by-one...")
                    for params in chunk:
                        try:
                            execute_sql(sql, params)
                            inserted += 1
                        except Exception as ex:
                            print(f"  Row error: {ex}")
                    break
        else:
            inserted += len(chunk)

        inserted += len(chunk)
        pct = int(inserted / total * 100)
        print(f"  ... {inserted}/{total} rows ({pct}%)", end="\r")

    print()
    return inserted


def main():
    source_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not source_path:
        candidates = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'inventory.db'),
            os.path.join(os.path.dirname(__file__), '..', 'inventory.db'),
            os.path.join(os.path.dirname(__file__), 'inventory.db'),
        ]
        for c in candidates:
            c = os.path.normpath(c)
            if os.path.exists(c):
                source_path = c
                break

    if not source_path or not os.path.exists(source_path):
        print("ERROR: source database not found")
        print("Usage: python migrate_builtin.py path/to/inventory.db")
        return 1

    print(f"Source: {source_path}")
    print(f"Target: {HOST}")
    print()

    src = sqlite3.connect(source_path)
    src.row_factory = sqlite3.Row

    # Step 1: Test connection
    print("Testing Turso connection...")
    try:
        result = execute_sql("SELECT 1 as test")
        print("  Connection OK!")
    except Exception as e:
        print(f"  Connection FAILED: {e}")
        return 1

    # Step 2: Create tables
    print("\nCreating tables on Turso...")
    for table in TABLES:
        ddl = DDL[table]
        try:
            execute_sql(ddl)
            print(f"  -> {table}: created")
        except Exception as e:
            print(f"  ! {table}: {e}")

    # Step 3: Migrate data
    print("\nMigrating data...")
    totals = {}
    for table in TABLES:
        rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
        if not rows:
            print(f"  -> {table}: 0 rows (empty)")
            totals[table] = 0
            continue

        cols = [desc[0] for desc in src.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(f'"{c}"' for c in cols)
        insert_sql = f'INSERT OR IGNORE INTO "{table}" ({col_names}) VALUES ({placeholders})'

        params_list = []
        for row in rows:
            vals = []
            for v in row:
                if v is None:
                    vals.append(None)
                else:
                    vals.append(str(v) if not isinstance(v, (int, float)) else v)
            params_list.append(tuple(vals))

        inserted = execute_batch(insert_sql, params_list)
        print(f"  -> {table}: {inserted} rows inserted")
        totals[table] = inserted

    # Step 4: Verify
    print("\nVerifying row counts...")
    for table in TABLES:
        result = execute_sql(f'SELECT COUNT(*) as cnt FROM "{table}"')
        try:
            count = result["results"][0]["response"]["result"]["rows"][0][0]
        except (KeyError, IndexError):
            count = "?"
        local_count = totals.get(table, "?")
        print(f"  {table}: local={local_count}, turso={count}")

    src.close()
    print("\nMigration complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
