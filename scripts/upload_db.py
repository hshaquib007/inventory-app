"""Upload the prepared SQLite database to Turso."""
import urllib.request
import urllib.error
import os
import json

DATABASE_URL = "libsql://inventory-hshaquib007.aws-ap-south-1.turso.io"
AUTH_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODg1MzU1NDYsImlkIjoiMDFhMDZkMDMtOWEwMS03NDY3LWFkMTgtZTRiZWI5YjFiMjYxIiwia2lkIjoib1llTExYZXBuaFA3SGhwMjZXODdyWWRENjRGdGFqb2hWZGxtUTR6bXpKUSIsInJpZCI6IjRkNTFlOWM4LTNjYTUtNDYxNy04ZTFlLWFkNzYwN2FiNzdiYSJ9.HAJ5hLLCyAhq4Xu3A3xnin2uZhoNg-zSF5crC11rpKQx9zbzQnVKqv65TJb5mxWcKwSPi-RlTEYYikvwzpEAAA"
HOST = DATABASE_URL.replace("libsql://", "https://")

DB_PATH = r"C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026\upload.db"

# Read the file
with open(DB_PATH, "rb") as f:
    data = f.read()

print(f"File size: {len(data):,} bytes ({len(data)/1024/1024:.1f} MB)")
print(f"Uploading to: {HOST}/v1/upload")

url = f"{HOST}/v1/upload"
req = urllib.request.Request(
    url,
    data=data,
    headers={
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Length": str(len(data)),
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=300) as resp:
        print(f"SUCCESS! Status: {resp.status}")
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print(f"HTTP {e.code}: {body}")
except Exception as e:
    print(f"Error: {e}")
