"""Search Data — cross-module data matrix for an item and/or job.

Final Balance = (opening_stock + received_from_GRN) − (pmi_issued + reserved_qty).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from sqlalchemy import func

import db
from db import (ItemMaster, PRNLine, GRNLine, PMILine, BOMLine, get_session)

st.set_page_config(page_title="Search Data", layout="wide")
st.title("Search Data")
st.caption("Cross-module ledger for a chosen item and/or job.")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

Session = get_session()


def lookup():
    results = []
    # Aggregate per item
    items = Session.query(ItemMaster).order_by(ItemMaster.item_code).all()

    grn = Session.query(GRNLine.item_code, func.sum(GRNLine.received_qty).label('v')) \
        .group_by(GRNLine.item_code).all()
    grn_map = {r.item_code: float(r.v or 0) for r in grn}

    pmi = Session.query(PMILine.item_code, func.sum(PMILine.received_qty).label('v')) \
        .group_by(PMILine.item_code).all()
    pmi_map = {r.item_code: float(r.v or 0) for r in pmi}

    prn = Session.query(PRNLine.item_code, func.sum(PRNLine.prn_qty).label('v')) \
        .group_by(PRNLine.item_code).all()
    prn_map = {r.item_code: float(r.v or 0) for r in prn}

    reserved = Session.query(PRNLine.item_code, func.sum(PRNLine.reserved_qty).label('v')) \
        .group_by(PRNLine.item_code).all()
    reserv_map = {r.item_code: float(r.v or 0) for r in reserved}

    bom = Session.query(BOMLine.item_code, func.sum(BOMLine.quantity).label('v')) \
        .group_by(BOMLine.item_code).all()
    bom_map = {r.item_code: float(r.v or 0) for r in bom}

    for it in items:
        opening = it.opening_stock or 0.0
        received = grn_map.get(it.item_code, 0.0)
        pmi_qty = pmi_map.get(it.item_code, 0.0)
        final_balance = (opening + received) - (pmi_qty + reserv_map.get(it.item_code, 0.0))
        results.append({
            'item_code': it.item_code, 'product_code': it.product_code,
            'item_name': it.item_name, 'uom': it.uom, 'opening_stock': opening,
            'prn_qty': prn_map.get(it.item_code, 0.0), 'received_qty': received,
            'pmi_qty': pmi_qty, 'bom_qty': bom_map.get(it.item_code, 0.0),
            'reserved_qty': reserv_map.get(it.item_code, 0.0),
            'final_balance': round(final_balance, 2),
        })
    return pd.DataFrame(results)


with st.spinner("Building ledger…"):
    df = lookup()

st.subheader("Filters")
c1, c2 = st.columns(2)
fitem = c1.text_input("Filter by Item Code or Name")
fjobs = c2.text_input("Filter by Job No (matches items present in that job)")

if fitem:
    df = df[df['item_code'].astype(str).str.contains(fitem, na=False) |
            df['item_name'].astype(str).str.contains(fitem, na=False) |
            df['product_code'].astype(str).str.contains(fitem, na=False)]
if fjobs:
    items_in_job = set(r.item_code for r in
                       Session.query(PRNLine.item_code).filter(
                           PRNLine.job_no.ilike(f'%{fjobs}%')).all())
    items_in_job |= set(r.item_code for r in
                        Session.query(GRNLine.item_code).filter(
                            GRNLine.job_no.ilike(f'%{fjobs}%')).all())
    items_in_job |= set(r.item_code for r in
                        Session.query(PMILine.item_code).filter(
                            PMILine.job_no.ilike(f'%{fjobs}%')).all())
    items_in_job |= set(r.item_code for r in
                        Session.query(BOMLine.item_code).filter(
                            BOMLine.job_no.ilike(f'%{fjobs}%')).all())
    df = df[df['item_code'].isin(items_in_job)]

st.caption(f"Showing {len(df):,} items")
st.dataframe(df, use_container_width=True, hide_index=True)

Session.close()