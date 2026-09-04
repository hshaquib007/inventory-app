# Resume Here — Deploy the Streamlit Inventory App

> **How to use this file:** When you reopen VS Code after a shutdown and start a fresh session,
> tell the assistant: *"Read `streamlit_app/RESUME_HERE.md` and continue."* It will re-orient instantly.

## Project
- Flask inventory app lives at root (`C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026`
  -> `app.py`, `templates/`, plus `glitch_deploy/` copy).
- A parallel **Streamlit app** was built at `streamlit_app/` with full feature parity.
- Data source of truth = **hosted Turso/libSQL** (chosen by user) so all PCs share live data.
- Real DB: `C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026\inventory.db` (22 MB, 10 tables).

## Status (all DONE and verified)
- [x] Built `streamlit_app/` (app.py, db.py, ui.py, utils.py, pages/*, scripts/migrate_to_turso.py).
- [x] All .py files compile (python 3.14).
- [x] Fixed FK bug: added ForeignKey to BOMLine/PRNLine/GRNLine/PMILine `*_id` columns.
- [x] Migration validated: copies all 10 tables, preserves IDs, row counts match
      (item_master 2833, bom_lines 12850, grn_lines 93689, prn_lines 65, etc.).
- [x] Reports verified vs real data (BOM vs Issue 12850 rows; PRN 65 / GRN 90207 groups).
- [x] Imports verified (item/job/BOM/GRN import + persist + stock side-effects).
- [ ] NOT done: local streamlit UI test (streamlit not installed on py3.14; pip timed out).
- [ ] NOT done: live Turso DB, migration to hosted, GitHub push, Streamlit Cloud deploy.

## YOUR deployment steps (after 18h) — the remaining work
1. **Install Turso CLI on your PC** (Optional; dashboard works too):
   - https://docs.turso.tech/cli
   - `turso auth login`
   - `turso db create inventory`
   - `turso db show inventory`  -> copy DB URL
   - `turso db tokens create inventory` -> copy auth token
2. **Fill secrets** — copy template, then edit:
   - `copy .streamlit\secrets.toml.example .streamlit\secrets.toml`
   - set `TURSO_DATABASE_URL = "libsql://..."` and `TURSO_AUTH_TOKEN = "eyJ..."`
   - (db.py auto-uses Turso if these are set; else falls back to local inventory.db)
3. **One-time data migration:**
   - `cd streamlit_app`
   - `python scripts\migrate_to_turso.py`
4. **Push to GitHub** (secrets + inventory.db are gitignored):
   - `git init; git add .; git commit -m "Inventory app"`
   - `git remote add origin https://github.com/<you>/<repo>.git`
   - `git push -u origin main`
5. **Deploy on Streamlit Cloud** (free, exposes app to another PC):
   - https://streamlit.io/cloud -> link GitHub -> pick repo
   - Path to main file = **`app.py`** (uses multipage `pages/` layout)
   - Settings -> Secrets: add `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN`
6. **Use/share:** open the public URL; sidebar has pages (Item/Job/BOM/PRN/GRN/PMI/Stock/Imports/Reports/Search).
   Imports & master edits write straight to Turso -> live on every machine.

## Key files
- `streamlit_app\db.py` - models (10 tables) + Turso/local SQLite connection.
- `streamlit_app\app.py` - dashboard launcher.
- `streamlit_app\pages\*` - the 10 feature pages.
- `streamlit_app\scripts\migrate_to_turso.py` - inventory.db -> Turso migration.
- `streamlit_app\README.md` - full setup/deploy docs.
- `streamlit_app\requirements.txt` - deps (streamlit, pandas, sqlalchemy, libsql).

## Gotchas encountered
- streamlit NOT installed on this Python 3.14 (pip install timed out) -> couldn't smoke-test UI locally.
- Dale: report outerjoins needed explicit `on` conditions (models have no FK constraints in DB);
  fixed by adding ForeignKey to the line models in db.py.