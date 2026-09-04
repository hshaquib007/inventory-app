"""Create Turso database + upload SQLite file in one shot."""
import urllib.request, urllib.error, json, os, time

PLATFORM_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJqdGkiOiJ5SjVwbDZoX0VmRzhJVVp4ZmhPQVN3Iiwib3JnX2lkIjoxMDAwMjM2NDU4fQ.BhfLp3H60UysJZwP_WiJYMt1wVF0QCWd-5JOoihceZe0UatO3gXxl4T5kJhyWHA45FnlPdtXbbFu6HLS_IChCQ"
ORG = "hshaquib007"
DB_NAME = "inventory"
DB_PATH = r"C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026\upload.db"

def api_call(method, url, data=None, token=None, timeout=60):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}")
        raise

# Step 1: Create database with upload seed
print("[1/3] Creating database with upload seed...")
try:
    result = api_call("POST", f"https://api.turso.tech/v1/organizations/{ORG}/databases",
        {"name": DB_NAME, "group": "default", "seed": {"type": "database_upload"}}, PLATFORM_TOKEN)
    print(f"  Created: {result.get('name', DB_NAME)}")
    hostname = result.get("hostname", f"{DB_NAME}-{ORG}.aws-ap-south-1.turso.io")
    print(f"  Hostname: {hostname}")
except Exception as e:
    print(f"  May already exist, checking...")
    # Try to list databases
    result = api_call("GET", f"https://api.turso.tech/v1/organizations/{ORG}/databases", token=PLATFORM_TOKEN)
    for db in result.get("databases", []):
        if db.get("name") == DB_NAME:
            hostname = db.get("hostname", f"{DB_NAME}-{ORG}.aws-ap-south-1.turso.io")
            print(f"  Found existing: {hostname}")
            break
    else:
        print("  FATAL: Could not create or find database")
        exit(1)

time.sleep(2)

# Step 2: Create auth token for the database
print("\n[2/3] Creating database auth token...")
result = api_call("POST",
    f"https://api.turso.tech/v1/organizations/{ORG}/databases/{DB_NAME}/auth/tokens",
    {}, PLATFORM_TOKEN)
db_token = result.get("jwt", "")
print(f"  Token: {db_token[:30]}...")

# Step 3: Upload the SQLite file
print(f"\n[3/3] Uploading {os.path.getsize(DB_PATH):,} bytes...")
with open(DB_PATH, "rb") as f:
    data = f.read()

url = f"https://{hostname}/v1/upload"
req = urllib.request.Request(url, data=data, headers={
    "Authorization": f"Bearer {db_token}",
    "Content-Length": str(len(data)),
}, method="POST")

try:
    with urllib.request.urlopen(req, timeout=300) as resp:
        print(f"  Upload SUCCESS! Status: {resp.status}")
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"  Upload HTTP {e.code}: {body}")
    exit(1)

print("\nDone! Updating secrets.toml...")
secrets_path = r"C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026\streamlit_app\.streamlit\secrets.toml"
with open(secrets_path, "w") as f:
    f.write(f'[turso]\ndatabase_url = "libsql://{hostname}"\nauth_token   = "{db_token}"\n')
print(f"  Saved to {secrets_path}")
print(f"\nFinal URL: libsql://{hostname}")
print(f"Token: {db_token}")
