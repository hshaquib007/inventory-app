"""Stock Management — view stock and edit opening/grn/issued quantities."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import ItemMaster, get_session
import ui

st.set_page_config(page_title="Stock Management", layout="wide")
st.title("Stock Management")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

Session = get_session()
items = Session.query(ItemMaster).order_by(ItemMaster.item_name).all()
df = pd.DataFrame([db.row_to_dict(r) for r in items])
for r in items:
    pass
# stock_quantity is a property; add it to the frame
recs = []
for r in items:
    d = db.row_to_dict(r)
    d['stock_quantity'] = r.stock_quantity
    recs.append(d)
df = pd.DataFrame(recs)
Session.close()

st.caption("Stock Quantity = Opening Stock + GRN Qty − Issued Qty")
st.caption(f"Total items: {len(df):,}")

filters = ui.text_filters(
    ["item_code", "product_code", "item_name", "opening_stock", "grn_qty",
     "issued_qty", "stock_quantity"], "stock"
)
fd = ui.apply_filters(df, filters, numeric_cols=["opening_stock", "grn_qty", "issued_qty", "stock_quantity"])
ui.show_table(fd, key="stock_grid")

st.divider()
st.subheader("Edit stock quantity")
options = df["item_code"].tolist()
sel = st.selectbox("Select Item Code", options, key="stock_edit_sel")
row = df[df["item_code"] == sel].iloc[0]
with st.form("edit_stock"):
    c1, c2, c3 = st.columns(3)
    e_open = c1.number_input("Opening Stock", value=float(row["opening_stock"] or 0.0))
    e_grn = c2.number_input("GRN Qty", value=float(row["grn_qty"] or 0.0))
    e_issued = c3.number_input("Issued Qty", value=float(row["issued_qty"] or 0.0))
    st.caption(f"Computed Stock Quantity: {(e_open or 0) + (e_grn or 0) - (e_issued or 0):.2f}")
    if st.form_submit_button("Save Changes"):
        s = get_session()
        obj = s.query(ItemMaster).filter_by(item_code=sel).first()
        obj.opening_stock = e_open
        obj.grn_qty = e_grn
        obj.issued_qty = e_issued
        s.commit()
        s.close()
        st.success("Stock updated.")
        st.rerun()

st.download_button(
    "Export Stock to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="stock_management.csv",
    mime="text/csv",
)