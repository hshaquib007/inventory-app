# Inventory System — Streamlit App (Cloud-synced)

A cross-PC version of the inventory management system. Instead of a local
SQLite file, the data lives in a hosted **Turso/libSQL** cloud database, so
every PC/network sees the **same live, saved data** — including file imports
and manual edits.

- **Dashboard** — KPIs across all modules
- **Item Master** — view/add/edit/delete items
- **Job Master** — view/add/edit/delete jobs
- **BOM / PRN / GRN / PMI** — view, create, delete (with stock effects)
- **Stock Management** — view & edit opening/GRN/issued stock
- **Imports** — upload CSV/Excel files (same format as the desktop app)
- **Reports** — BOM vs Issue, PRN vs Receipt
- **Search Data** — cross-module item/job ledger

---

## 1. Create the cloud database (free, one-time)

1. Sign up at https://turso.tech and install the CLI:
   ```bash
   brew install tursodatabase/tap/turso   # macOS
   # or on Windows, use the installer from the Turso site
   ```

2. Create a database and an auth token:
   ```bash
   turso auth login
   turso db create inventory
   turso db show inventory                    # copy the database URL
   turso db tokens create inventory           # copy the auth token
   ```

## 2. Configure secrets

```bash
cd streamlit_app
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```
Then open `.streamlit/secrets.toml` and paste your Turso URL and token.

## 3. (One time) migrate your existing data into the cloud

Point this at your current database file and it copies all 10 tables into Turso
(schema preserved, IDs preserved):

```bash
cd streamlit_app
pip install -r requirements.txt
python scripts/migrate_to_turso.py "C:\path\to\your\inventory.db"
```
Add `--reset` to wipe the cloud tables before copying (use with care).

Verify it worked by checking the printed row counts.

## 4. Run the app

```bash
cd streamlit_app
python -m streamlit run app.py
```
Open the printed URL (default http://localhost:8501).

## 5. Upload to GitHub

Create a new GitHub repo (public or private, e.g. `inventory-streamlit`) and push
**the `streamlit_app` folder**:

```bash
cd streamlit_app
git init
git add .
git commit -m "Inventory Streamlit app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/inventory-streamlit.git
git push -u origin main
```
> `.gitignore` already excludes `.streamlit/secrets.toml` so your token is **not** uploaded.

## 6. Deploy to Streamlit Community Cloud (free, public URL)

1. Go to https://share.streamlit.io
2. Sign in with GitHub and **Deploy an app** → choose your repo, main branch, and `app.py`.
3. In **App Settings → Secrets**, paste the same `[turso]` block.
4. Open the published URL (e.g. `https://inventory-streamlit.streamlit.app`) from **any PC/network**.

Every PC that visits the public URL (or runs it locally with the same secrets)
reads and writes the same Turso database, so imports and manual edits are shared
and saved.

---

## Notes / safety
- The free Streamlit Community Cloud **disk resets** on redeploy — that is why the
  database lives in Turso, not on the local disk. Do **not** store data in
  `st.session_state` or local files as the source of truth.
- Deleting data is permanent (there is no undo). The original desktop app's
  `inventory.db` remains your full backup.