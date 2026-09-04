"""
One-time migration: copy the existing local SQLite database into a hosted
Turso/libSQL database so the Streamlit app starts from your current data.

Usage:
    python scripts/migrate_to_turso.py [source_db_path]

The source database defaults to the root `inventory.db` next to the app.

It reads from the local SQLite file and writes into Turso using the same
connection configured for the Streamlit app (secrets.toml or env vars).
Existing target rows are NOT deleted unless you pass --reset.

Examples:
    python scripts/migrate_to_turso.py
    python scripts/migrate_to_turso.py "C:\\path\\to\\inventory.db"
    python scripts/migrate_to_turso.py --reset   # wipe Turso tables first
"""

import os
import sys
from datetime import datetime, date

# Make `import db`/`import utils` work from anywhere
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
import db as appdb


# Tables in dependency order (parents before children so inserts are FK-safe).
TABLES = [
    'item_master',   # independent
    'job_master',    # independent
    'bom',           # parent of bom_lines
    'bom_lines',
    'grn',           # parent of grn_lines
    'grn_lines',
    'prn',           # parent of prn_lines
    'prn_lines',
    'pmi',           # parent of pmi_lines
    'pmi_lines',
]

# Reverse order (children before parents) used when wiping before a reset.
TABLES_REVERSED = list(reversed(TABLES))


def _norm(value):
    """Normalize a value for a portable copy.

    SQLite stores DATE/DATETIME values as ISO strings, so reading them via
    Core `text()` already returns strings (and None for NULL). We pass those
    straight through so the target stores identical values. Plain datetime
    objects (only possible when read through the ORM) are converted to ISO.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S.%f')
    return value


def copy_table(src_conn, dst_conn, table, engine_dst):
    """Copy all rows from a source table to the target table preserving ids."""
    # Discover source columns
    src_cols = [r[1] for r in src_conn.execute(text(f'PRAGMA table_info("{table}")'))]
    if not src_cols:
        print(f"  ! source table '{table}' has no columns, skipping")
        return 0

    # Discover existing max id in target to avoid primary-key collisions
    max_id = None
    if 'id' in src_cols:
        try:
            max_id = dst_conn.execute(text(f'SELECT MAX(id) FROM "{table}"')).scalar()
        except Exception:
            max_id = None

    rows = src_conn.execute(text(f'SELECT * FROM "{table}"')).fetchall()
    count = 0
    skipped = 0

    for row in rows:
        vals = [_norm(v) for v in row]
        values_map = dict(zip(src_cols, vals))

        # Skip rows whose id already exists in target (upsert guard)
        if max_id is not None and 'id' in values_map and values_map['id'] is not None:
            existing = dst_conn.execute(
                text(f'SELECT id FROM "{table}" WHERE id = :id'), {'id': values_map['id']}
            ).fetchone()
            if existing:
                skipped += 1
                continue

        cols = ', '.join(f'"{c}"' for c in src_cols)
        placeholders = ', '.join(f':{c}' for c in src_cols)
        try:
            dst_conn.execute(text(f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})'), values_map)
            count += 1
        except Exception as e:
            print(f"  ! row error in {table} id={values_map.get('id')}: {e}")
            skipped += 1

    return count


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    reset = '--reset' in sys.argv

    source_path = args[0] if args else None
    if not source_path:
        # Default: root inventory.db next to this repo
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(here)), 'inventory.db'),  # ../inventory.db
            os.path.join(here, 'inventory.db'),
            os.path.join('instance', 'inventory.db'),
        ]
        source_path = next((c for c in candidates if os.path.exists(c)), None)

    if not source_path or not os.path.exists(source_path):
        print("ERROR: could not find a source SQLite database.")
        print("Pass it explicitly:  python scripts/migrate_to_turso.py path/to/inventory.db")
        return 1

    # Build target connection (Turso via the app's db module)
    url, token = appdb._get_connection_params()
    if not url:
        print("ERROR: no Turso database configured.")
        print("Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN (or .streamlit/secrets.toml).")
        return 1

    print(f"Source : {source_path}")
    print(f"Target : {url}")
    if reset:
        print("Mode   : RESET (target tables will be wiped & recreated)")

    src = create_engine(f'sqlite:///{os.path.abspath(source_path)}')
    src_conn = src.connect()

    dst = appdb.build_engine()
    dst_conn = dst.connect()

    # Ensure schema exists on target
    appdb.Base.metadata.create_all(dst)
    dst_conn.commit()

    totals = {}
    if reset:
        # Children first, then parents
        for table in TABLES_REVERSED:
            try:
                dst_conn.execute(text(f'DELETE FROM "{table}"'))
                print(f"  -- reset table {table}")
            except Exception as e:
                print(f"  ! could not reset {table}: {e}")
        dst_conn.commit()

    for table in TABLES:
        n = copy_table(src_conn, dst_conn, table, dst)
        totals[table] = n
        print(f"  -> {table}: {n} rows copied")

    dst_conn.commit()
    print("\nMigration complete.")
    for t, n in totals.items():
        total_in_target = dst_conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        print(f"  {t}: copied={n}, total in target={total_in_target}")

    src_conn.close()
    dst_conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
