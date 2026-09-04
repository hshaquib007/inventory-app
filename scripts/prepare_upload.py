import sqlite3, shutil, os

src = r'C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026\inventory.db'
dst = r'C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026\upload.db'

shutil.copy2(src, dst)

db = sqlite3.connect(dst)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
db.execute("PRAGMA page_size=4096")
db.execute("PRAGMA auto_vacuum=0")
db.execute("PRAGMA encoding='UTF-8'")
db.commit()
db.close()

size = os.path.getsize(dst)
print(f"Prepared: {dst}")
print(f"Size: {size:,} bytes ({size/1024/1024:.1f} MB)")
