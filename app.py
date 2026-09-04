"""
Streamlit Inventory Management System
=====================================
A cross-PC, cloud-synced Streamlit version of the inventory app.

Data lives in a hosted Turso/libSQL database so every PC/network shares the
same live data. On Streamlit Community Cloud the app reads the connection
from `.streamlit/secrets.toml`.

Run locally:
    python -m streamlit run app.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd

import db
from db import (ItemMaster, JobMaster, BOM, BOMLine, PRN, PRNLine,
                GRN, GRNLine, PMI, PMILine, get_session)


def _df(rows):
    return pd.DataFrame([db.row_to_dict(r) for r in rows])


st.set_page_config(page_title="Inventory System", page_icon="📦", layout="wide")

# Try to connect up-front so a misconfiguration surfaces immediately.
try:
    Session = db.init_db()
    st.session_state['db_ok'] = True
except Exception as e:
    st.session_state['db_ok'] = False
    st.error(f"Database connection failed: {e}")

st.title("📦 Inventory Management System")
st.caption("Cloud-synced via Turso/libSQL — accessible from any PC/network.")

if not st.session_state.get('db_ok', False):
    st.stop()

with st.spinner("Loading dashboard…"):
    Session = db.get_session()
    try:
        total_items = Session.query(ItemMaster).count()
        total_jobs = Session.query(JobMaster).count()
        total_bom = Session.query(BOMLine).count()
        total_grn = Session.query(GRNLine).count()
        total_prn = Session.query(PRNLine).count()
        total_pmi = Session.query(PMILine).count()
        opening = (Session.query(db.func.coalesce(
            db.func.sum(ItemMaster.opening_stock), 0)).scalar() or 0)
        Session.close()
    except Exception as e:
        Session.close()
        st.error(f"Could not load dashboard: {e}")
        st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Item Master", f"{total_items:,}")
c2.metric("Job Master", f"{total_jobs:,}")
c3.metric("BOM Lines", f"{total_bom:,}")
c4.metric("GRN Lines", f"{total_grn:,}")

c5, c6, c7, c8 = st.columns(4)
c5.metric("PRN Lines", f"{total_prn:,}")
c6.metric("PMI Lines", f"{total_pmi:,}")
c7.metric("Opening Stock", f"{opening:,.1f}")
c8.metric("Data Source", "Turso/libSQL" if db._get_connection_params()[0] else "Local SQLite")

st.divider()
st.subheader("Quick Actions")
st.caption("Use the pages in the left sidebar to manage each module: "
           "Item Master, Job Master, BOM, PRN, GRN, PMI, Stock, Imports and Reports.")
