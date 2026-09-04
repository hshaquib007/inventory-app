"""Reports — BOM vs Issue and PRN vs Receipt comparisons."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from sqlalchemy import func, or_

import db
from db import BOMLine, PMILine, PRNLine, GRNLine, get_session

st.set_page_config(page_title="Reports", layout="wide")
st.title("Reports")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

report = st.radio("Choose report", ["BOM vs Issue", "PRN vs Receipt"], horizontal=True)

Session = get_session()


def load_bom_vs_issue():
    rows = (Session.query(
        BOMLine.bom_sr_no, BOMLine.job_no, BOMLine.item_code, BOMLine.product_code,
        BOMLine.item_name, BOMLine.uom, BOMLine.quantity,
        func.coalesce(func.sum(PMILine.received_qty), 0).label('issued_quantity'),
        BOMLine.group, BOMLine.sub_group,
    ).outerjoin(PMILine, (BOMLine.item_code == PMILine.item_code) & (BOMLine.job_no == PMILine.job_no))
        .group_by(BOMLine.id)
        .all())
    recs = []
    for r in rows:
        issued = float(r.issued_quantity)
        balance = float(r.quantity) - issued
        recs.append({
            'bom_sr_no': r.bom_sr_no, 'job_no': r.job_no, 'item_code': r.item_code,
            'product_code': r.product_code, 'item_name': r.item_name, 'uom': r.uom,
            'bom_quantity': r.quantity, 'issued_quantity': issued, 'balance_quantity': balance,
            'group': r.group, 'sub_group': r.sub_group,
        })
    return pd.DataFrame(recs)


def load_prn_vs_receipt():
    prn_rows = (Session.query(
        PRNLine.item_code, PRNLine.product_code, PRNLine.item_name, PRNLine.uom,
        PRNLine.job_no, func.sum(PRNLine.prn_qty).label('prn_qty'))
        .filter(PRNLine.job_no.isnot(None), PRNLine.prn_qty > 0)
        .group_by(PRNLine.item_code, PRNLine.job_no)
        .all())
    grn_rows = (Session.query(
        GRNLine.item_code, GRNLine.job_no, func.sum(GRNLine.received_qty).label('received_qty'))
        .filter(GRNLine.job_no.isnot(None))
        .group_by(GRNLine.item_code, GRNLine.job_no)
        .all())
    grn_map = {(r.item_code, r.job_no): float(r.received_qty or 0) for r in grn_rows}
    recs = []
    for r in prn_rows:
        received = grn_map.get((r.item_code, r.job_no), 0.0)
        prn_qty = float(r.prn_qty)
        recs.append({
            'item_code': r.item_code, 'product_code': r.product_code, 'item_name': r.item_name,
            'uom': r.uom, 'job_no': r.job_no, 'prn_qty': prn_qty,
            'received_qty': received, 'balance_qty': prn_qty - received,
        })
    return pd.DataFrame(recs)


if report == "BOM vs Issue":
    st.subheader("BOM vs Issue")
    st.caption("Compares BOM required quantity against issued quantity (from PMI). "
               "Balance = BOM − Issued.")
    df = load_bom_vs_issue()
    tab = st.radio("Status", ["All", "Pending Issue", "Fully Issued", "Over Issued"], horizontal=True)
    if tab == "Pending Issue":
        df = df[df['balance_quantity'] > 0]
    elif tab == "Fully Issued":
        df = df[df['balance_quantity'] == 0]
    elif tab == "Over Issued":
        df = df[df['balance_quantity'] < 0]
    col1, col2, col3 = st.columns(3)
    # simpler filters
    fjob = st.text_input("Job No filter")
    if fjob:
        df = df[df['job_no'].astype(str).str.contains(fjob, na=False)]
    fitem = st.text_input("Item Code / Name filter")
    if fitem:
        df = df[df['item_code'].astype(str).str.contains(fitem, na=False) |
                df['item_name'].astype(str).str.contains(fitem, na=False)]
    st.caption(f"Showing {len(df):,} records")
    st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.subheader("PRN vs Receipt")
    st.caption("Compares PRN quantity against GRN received quantity. "
               "Balance = PRN − Received.")
    df = load_prn_vs_receipt()
    tab = st.radio("Status", ["All", "Pending PRN", "Fully received", "Over receipt"], horizontal=True)
    if tab == "Pending PRN":
        df = df[df['balance_qty'] > 0]
    elif tab == "Fully received":
        df = df[df['balance_qty'] == 0]
    elif tab == "Over receipt":
        df = df[df['balance_qty'] < 0]
    fsearch = st.text_input("Search item/job filter")
    if fsearch:
        df = df[df['item_code'].astype(str).str.contains(fsearch, na=False) |
                df['item_name'].astype(str).str.contains(fsearch, na=False) |
                df['job_no'].astype(str).str.contains(fsearch, na=False)]
    st.caption(f"Showing {len(df):,} records")
    st.dataframe(df, use_container_width=True, hide_index=True)

Session.close()