"""
Fast migration: dump SQLite to SQL file, then batch-execute on Turso.
"""
import sqlite3
import json
import urllib.request
import urllib.error
import sys
import os
import time

DATABASE_URL = "libsql://inventory-hshaquib007.aws-ap-south-1.turso.io"
AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODg1MzU1NDYsImlkIjoiMDFhMDZkMDMtOWEwMS03NDY3LWFkMTgtZTRiZWI5YjFiMjYxIiwia2lkIjoib1llTExYZXBuaFA3SGhwMjZXODdyWWRENjRGdGFqb2hWZGxtUTR6bXpKUSIsInJpZCI6IjRkNTFlOWM4LTNjYTUtNDYxNy04ZTFlLWFkNzYwN2FiNzdiYSJ9.HAJ5hLLCyAhq4Xu3A3xnin2uZhoNg-zSF5crC11rpKQx9zbzQnVKqv65TJb5mxWcKwSPi-RlTEYYikvwzpEAAA"
HOST = DATABASE_URL.replace("libsql://", "https://")

TABLES = ['item_master','job_master','bom','bom_lines','grn','grn_lines','prn','prn_lines','pmi','pmi_lines']

DDL = {
    'item_master': """CREATE TABLE IF NOT EXISTS item_master (id INTEGER PRIMARY KEY, item_code TEXT UNIQUE NOT NULL, product_code TEXT NOT NULL, item_name TEXT NOT NULL, uom TEXT NOT NULL, opening_stock REAL DEFAULT 0.0, grn_qty REAL DEFAULT 0.0, issued_qty REAL DEFAULT 0.0, "group" TEXT, sub_group TEXT, created_at TEXT, updated_at TEXT)""",
    'job_master': """CREATE TABLE IF NOT EXISTS job_master (id INTEGER PRIMARY KEY, job_no TEXT UNIQUE NOT NULL, job_detail TEXT NOT NULL, customer TEXT NOT NULL, job_group TEXT, created_at TEXT, updated_at TEXT)""",
    'bom': """CREATE TABLE IF NOT EXISTS bom (id INTEGER PRIMARY KEY, bom_no TEXT NOT NULL, job_no TEXT NOT NULL, job_group TEXT, date TEXT NOT NULL, created_at TEXT, updated_at TEXT)""",
    'bom_lines': """CREATE TABLE IF NOT EXISTS bom_lines (id INTEGER PRIMARY KEY, bom_id INTEGER NOT NULL, bom_sr_no TEXT, job_no TEXT, item_code TEXT NOT NULL, product_code TEXT NOT NULL, item_name TEXT NOT NULL, uom TEXT NOT NULL, quantity REAL NOT NULL, "group" TEXT, sub_group TEXT, revision TEXT DEFAULT '0', baseline_item_name TEXT, baseline_quantity REAL, created_at TEXT, updated_at TEXT, FOREIGN KEY (bom_id) REFERENCES bom(id))""",
    'grn': """CREATE TABLE IF NOT EXISTS grn (id INTEGER PRIMARY KEY, grn_no TEXT UNIQUE NOT NULL, grn_date TEXT NOT NULL, supplier_name TEXT, invoice_no TEXT, invoice_date TEXT, job_group TEXT, remarks TEXT, created_at TEXT, updated_at TEXT)""",
    'grn_lines': """CREATE TABLE IF NOT EXISTS grn_lines (id INTEGER PRIMARY KEY, grn_id INTEGER NOT NULL, item_code TEXT NOT NULL, product_code TEXT NOT NULL, item_name TEXT NOT NULL, uom TEXT NOT NULL, received_qty REAL NOT NULL, date TEXT NOT NULL, po_number TEXT, job_no TEXT, last_purchase_price REAL DEFAULT 0.0, created_at TEXT, updated_at TEXT, FOREIGN KEY (grn_id) REFERENCES grn(id))""",
    'prn': """CREATE TABLE IF NOT EXISTS prn (id INTEGER PRIMARY KEY, prn_no TEXT UNIQUE NOT NULL, prn_date TEXT NOT NULL, job_no TEXT NOT NULL, job_group TEXT, status TEXT DEFAULT 'Pending', remarks TEXT, created_at TEXT, updated_at TEXT)""",
    'prn_lines': """CREATE TABLE IF NOT EXISTS prn_lines (id INTEGER PRIMARY KEY, prn_id INTEGER NOT NULL, bom_no TEXT, bom_sr_no TEXT, item_code TEXT NOT NULL, product_code TEXT NOT NULL, item_name TEXT NOT NULL, uom TEXT NOT NULL, job_no TEXT, required_qty REAL NOT NULL, prn_qty REAL NOT NULL, reserved_qty REAL DEFAULT 0.0, stock_qty REAL DEFAULT 0.0, created_at TEXT, updated_at TEXT, FOREIGN KEY (prn_id) REFERENCES prn(id))""",
    'pmi': """CREATE TABLE IF NOT EXISTS pmi (id INTEGER PRIMARY KEY, pmi_no TEXT UNIQUE NOT NULL, pmi_date TEXT NOT NULL, supplier_name TEXT, invoice_no TEXT, invoice_date TEXT, job_group TEXT, remarks TEXT, created_at TEXT, updated_at TEXT)""",
    'pmi_lines': """CREATE TABLE IF NOT EXISTS pmi_lines (id INTEGER PRIMARY KEY, pmi_id INTEGER NOT NULL, item_code TEXT NOT NULL, product_code TEXT NOT NULL, item_name TEXT NOT NULL, uom TEXT NOT NULL, received_qty REAL NOT NULL, date TEXT NOT NULL, job_no TEXT, created_at TEXT, updated_at TEXT, FOREIGN KEY (pmi_id) REFERENCES pmi(id))""",
}

def esc(v):
    if v is None:
        return "NULL"
    s = str(v).replace("'", "''")
    return f"'{s}'"

def execute_sql(sql, retries=3):
    url = f"{HOST}/v2/pipeline"
    payload = json.dumps({"requests": [{"type": "execute", "stmt": {"sql": sql}}]}).encode("utf-8")
    for attempt in range(retries):
        req = urllib.request.Request(url, data=payload, headers={"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if "error" in result.get("results", [{}])[0]:
                    print(f"  SQL error: {result['results'][0]['error']}")
                return result
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt+1}: {e}")
                time.sleep(3)
            else:
                raise

def execute_sql_batch(sql_list, retries=3):
    """Execute multiple SQL statements in one pipeline request."""
    url = f"{HOST}/v2/pipeline"
    requests = [{"type": "execute", "stmt": {"sql": s}} for s in sql_list]
    payload = json.dumps({"requests": requests}).encode("utf-8")
    for attempt in range(retries):
        req = urllib.request.Request(url, data=payload, headers={"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt+1}: {e}")
                time.sleep(3)
            else:
                raise

def main():
    source_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not source_path or not os.path.exists(source_path):
        print("Usage: python migrate_fast.py path/to/inventory.db")
        return 1

    print(f"Source: {source_path}")
    print(f"Target: {HOST}")

    # Step 1: Generate SQL dump
    print("\n[1/3] Generating SQL from local SQLite...")
    src = sqlite3.connect(source_path)
    dump_lines = []

    for table in TABLES:
        # Drop and create
        dump_lines.append(f'DROP TABLE IF EXISTS "{table}";')
        dump_lines.append(DDL[table])

    for table in TABLES:
        rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
        if not rows:
            print(f"  {table}: 0 rows (empty)")
            continue
        cols = [d[0] for d in src.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
        for row in rows:
            vals = []
            for v in row:
                vals.append(esc(v))
            col_names = ", ".join(f'"{c}"' for c in cols)
            dump_lines.append(f'INSERT INTO "{table}" ({col_names}) VALUES ({", ".join(vals)});')
        print(f"  {table}: {len(rows)} rows")

    src.close()
    total_stmts = len(dump_lines)
    print(f"\n  Total SQL statements: {total_stmts}")

    # Step 2: Create tables first
    print("\n[2/3] Creating tables on Turso...")
    create_stmts = []
    for table in TABLES:
        create_stmts.append(f'DROP TABLE IF EXISTS "{table}";')
        create_stmts.append(DDL[table])
    execute_sql_batch(create_stmts)
    print("  All 10 tables created!")

    # Step 3: Insert data in batches of statements
    print("\n[3/3] Inserting data...")
    # Skip the CREATE statements (first 20)
    insert_lines = dump_lines[20:]
    BATCH = 20  # statements per HTTP request
    done = 0
    total = len(insert_lines)

    for i in range(0, total, BATCH):
        chunk = insert_lines[i:i+BATCH]
        try:
            execute_sql_batch(chunk)
            done += len(chunk)
            pct = int(done / total * 100)
            print(f"  ... {done}/{total} ({pct}%)", end="\r")
        except Exception as e:
            print(f"\n  Error at batch {i}: {e}")
            # Try one by one
            for line in chunk:
                try:
                    execute_sql(line)
                    done += 1
                except:
                    pass

    print(f"\n  Done: {done}/{total} statements executed")

    # Verify
    print("\nVerifying counts on Turso...")
    for table in TABLES:
        result = execute_sql(f'SELECT COUNT(*) as cnt FROM "{table}"')
        try:
            count = result["results"][0]["response"]["result"]["rows"][0][0]
        except:
            count = "?"
        print(f"  {table}: {count}")

    print("\nMigration complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
