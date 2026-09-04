@echo off
cd /d "%~dp0"
set INVENTORY_DB_PATH=%~dp0inventory_local.db
".venv\Scripts\python.exe" -m streamlit run app.py
pause