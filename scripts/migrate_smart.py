"""
Migrate SQLite -> Turso via HTTP API.
Saves SQL dump to file first, then sends in small batches.
Supports resume: tracks last completed statement in progress file.
"""
import sqlite3, json, urllib.request, urllib.error, sys, os, time

DATABASE_URL = "libsql://inventory-hshaquib007.aws-ap-south-1.turso.io"
AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODg1MzU1NDYsImlkIjoiMDFhMDZkMDMtOWEwMS03NDY3LWFkMTgtZTRiZWI5YjFiMjYxIiwia2lkIjoib1llTExYZXBuaFA3SGhwMjZXODdyWWRENjRGdGFqb2hWZGxtUTR6bXpKUSIsInJpZCI6IjRkNTFlOWM4LTNjYTUtNDYxNy04ZTFlLWFkNzYwN2FiNzdiYSJ9.HAJ5hLLCyAhq4Xu3A3xnin2uZhoNg-zSF5crC11rpKQx9zbzQnVKqv65TJb5mxWcKwSPi-RlTEYYikvwzpEAAA"
HOST = DATABASE_URL.replace("libsql://", "https://")
DUMP_FILE = os.path.join(os.path.dirname(__file__), "dump.sql")
PROGRESS_FILE = os.path.join(os.path.dirname(__file__), "progress.txt")

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
    if v is None: return "NULL"
    return "'" + str(v).replace("'", "''") + "'"

def pipe_exec(sql, retries=3):
    url = f"{HOST}/v2/pipeline"
    payload = json.dumps({"requests": [{"type": "execute", "stmt": {"sql": sql}}]}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(url, data=payload,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt+1}: {e}")
                time.sleep(2)
            else:
                raise

def pipe_exec_multi(stmts, retries=3):
    url = f"{HOST}/v2/pipeline"
    requests = [{"type": "execute", "stmt": {"sql": s}} for s in stmts]
    payload = json.dumps({"requests": requests}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(url, data=payload,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt+1}: {e}")
                time.sleep(2)
            else:
                raise

def generate_dump(src_path):
    print("[Step 1] Generating SQL dump file...")
    src = sqlite3.connect(src_path)
    with open(DUMP_FILE, "w", encoding="utf-8") as f:
        for table in TABLES:
            f.write(f'DROP TABLE IF EXISTS "{table}";\n')
            f.write(DDL[table] + ";\n")
        for table in TABLES:
            rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
            if not rows:
                print(f"  {table}: empty")
                continue
            cols = [d[0] for d in src.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
            col_str = ", ".join(f'"{c}"' for c in cols)
            for row in rows:
                vals = ", ".join(esc(v) for v in row)
                f.write(f'INSERT INTO "{table}" ({col_str}) VALUES ({vals});\n')
            print(f"  {table}: {len(rows)} rows")
    src.close()
    with open(DUMP_FILE, "r", encoding="utf-8") as f:
        total = sum(1 for _ in f)
    print(f"  Dump saved: {DUMP_FILE} ({total} lines)")
    return total

def get_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return int(f.read().strip())
    return 0

def set_progress(n):
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(n))

def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not src_path or not os.path.exists(src_path):
        print("Usage: python migrate_smart.py path/to/inventory.db")
        return 1

    # Step 1: Generate dump if needed
    if not os.path.exists(DUMP_FILE):
        total = generate_dump(src_path)
    else:
        with open(DUMP_FILE, "r", encoding="utf-8") as f:
            total = sum(1 for _ in f)
        print(f"Using existing dump: {DUMP_FILE} ({total} lines)")

    # Step 2: Read all lines
    with open(DUMP_FILE, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]

    # Step 3: Find resume point
    done = get_progress()
    remaining = lines[done:]
    print(f"\n[Step 2] Executing on Turso ({done}/{total} already done, {len(remaining)} remaining)")

    if not remaining:
        print("Nothing to do - already complete!")
    else:
        BATCH = 25
        i = 0
        while i < len(remaining):
            chunk = remaining[i:i+BATCH]
            try:
                pipe_exec_multi(chunk)
                done += len(chunk)
                set_progress(done)
                pct = int(done / total * 100)
                print(f"  [{done}/{total}] {pct}%  ", end="\r")
                sys.stdout.flush()
                i += len(chunk)
            except Exception as e:
                print(f"\n  Error at {done}: {e}")
                # Try half batch
                half = BATCH // 2
                for j in range(0, len(chunk), half):
                    sub = chunk[j:j+half]
                    try:
                        pipe_exec_multi(sub)
                        done += len(sub)
                        set_progress(done)
                        i += len(sub)
                    except:
                        # One by one
                        for stmt in sub:
                            try:
                                pipe_exec(stmt)
                                done += 1
                                set_progress(done)
                                i += 1
                            except Exception as e2:
                                print(f"\n  Failed: {e2}")
                                print(f"  Resume: run again. Progress={done}/{total}")
                                return 1

    # Step 4: Verify
    print(f"\n\n[Step 3] Verifying...")
    for table in TABLES:
        result = pipe_exec(f'SELECT COUNT(*) FROM "{table}"')
        try:
            count = result["results"][0]["response"]["result"]["rows"][0][0]
        except:
            count = "?"
        print(f"  {table}: {count}")

    # Clean up
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    print("\nMigration complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
