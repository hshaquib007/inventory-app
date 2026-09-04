# Resume Here — Streamlit Inventory App (updated 04-Sep-2026)

> **How to use this file:** When you reopen VS Code and start a fresh session,
> tell the assistant: *"Read `streamlit_app/RESUME_HERE.md` and continue."* It will re-orient instantly.

## Status snapshot
- **Turso DB LIVE** with the user's real data (verified via pipeline query): item_master **2,833**,
  job_master 599, bom 2, bom_lines 12,850, grn 2,102, grn_lines 93,689, prn 1, prn_lines 65, pmi 2, pmi_lines 13.
  - URL: `libsql://inventory-hshaquib007.aws-ap-south-1.turso.io`
  - The DB auth token is in `.streamlit/secrets.toml` (gitignored). Platform token also exists.
- **GitHub repo**: `https://github.com/hshaquib007/inventory-app` (PUBLIC, branch `main`).
  - Local HEAD `3fdff2e`. NOTE: GitHub shows a newer commit `00e520a "Added Dev Container Folder"`
    that is NOT local — pull that when we resume (`git pull` or fetch).
- **Deployed**: `https://kasiooninventory-app.streamlit.app/` — LIVE but dashboard shows all **0s**.
- **Local**: `.venv` (Python 3.12) + `inventory_local.db` (a copy of the real DB) work;
  app runs at `http://localhost:8501` and shows real data.
- **Key discovery**: on Windows, `sqlalchemy-libsql==0.2.0` -> `libsql-experimental` has **no Windows wheel**
  (build-from-source needs Rust and fails). The newer `libsql` package DOES ship win_amd64 wheels (cp310-cp313),
  but sqlalchemy-libsql 0.2.0 pins `libsql-experimental`. Local Windows runs therefore use the local SQLite
  copy; Streamlit Cloud (Linux) uses Turso fine.

## The ONE outstanding problem
Deployed app shows 0s while the local app shows real data. Most likely the Streamlit Cloud **Secrets**
are not being read (wrong format/copy). Everything else (repo, code, DB) is confirmed correct.

### Next step when we resume
Ask/tell the assistant: the **"Data Source"** metric on the far right of the deployed dashboard — does it
say **"Turso/libSQL"** or **"Local SQLite"**?
- "Local SQLite" -> secrets not loaded -> re-paste Secrets exactly (see block below), app auto-restarts.
- "Turso/libSQL" -> secrets load but something else; then check connection/app restart.

### The secrets block that must be pasted into Streamlit Cloud
(app: Settings -> Secrets, then the app auto-restarts)

```toml
[turso]
database_url = "libsql://inventory-hshaquib007.aws-ap-south-1.turso.io"
auth_token   = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3ODg1NDAzMjcsImlkIjoiMDFhMDZkNGYtODYwMS03NzM4LWJhMWEtNDhiODY0MzFmMDBjIiwia2lkIjoib1llTExYZXBuaFA3SGhwMjZXODdyWWRENjRGdGFqb2hWZGxtUTR6bXpKUSIsInJpZCI6ImFlN2NlOTAzLTY0NjUtNDUzMi1iN2I2LWExMDljNjY5ZjhhZiJ9.KwEaeGTnAbEqRQq2A_8LbHDqLlUmR09PJP-iGEy7F1ezl-enmUs61VrSd4acpONS3kD6-Rwxj3qhX1WjjmYzDg"
```

### Local run (format comparison / development)
Double-click `run_local.bat` (or run at a terminal):
```
streamlit_app\run_local.bat
```
Then open http://localhost:8501. It reads `streamlit_app\inventory_local.db` (real copy).

## Key files
- `streamlit_app\app.py` - dashboard (shows Data Source metric at c8).
- `streamlit_app\db.py` - models + Turso/local SQLite connection (`_get_connection_params`, `build_engine`).
- `streamlit_app\.streamlit\secrets.toml` - Turso creds (gitignored; source of truth for the token).
- `streamlit_app\run_local.bat` - one-click local launch with the real local data.
- `streamlit_app\requirements.txt` - streamlit, pandas, SQLAlchemy, sqlalchemy-libsql==0.2.0.
- Source DB: `C:\Users\LENOVO\Desktop\INVENTORY FILE\30.06.2026\inventory.db`.

## Gotchas
- Local Windows: CANNOT pip-install sqlalchemy-libsql (no win wheel) — local uses SQLite copy.
- Python 3.14 on PC breaks pip for Turso packages; `.venv` uses Python 3.12.
- Do NOT commit `.streamlit/secrets.toml`, `*.db`, or `scripts/` files with tokens (gitignored).