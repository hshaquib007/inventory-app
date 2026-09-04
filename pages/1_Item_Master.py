"""Item Master — view, add, edit and delete items."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import ItemMaster, get_session
from utils import to_float
import ui

st.set_page_config(page_title="Item Master", layout="wide")
st.title("Item Master")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

Session = get_session()
st.cache_data.clear()

df = pd.DataFrame(
    [db.row_to_dict(r) for r in Session.query(ItemMaster).order_by(ItemMaster.item_name).all()]
)
Session.close()

if df.empty:
    st.info("No items found. Add some items or use the Imports page.")
    st.stop()

st.caption(f"Total items: {len(df):,}")

tab_view, tab_add, tab_edit, tab_delete = st.tabs(["View / Filter", "Add Item", "Edit Item", "Delete"])

with tab_view:
    filters = ui.text_filters(
        ["item_code", "product_code", "item_name", "uom", "opening_stock", "group", "sub_group"],
        "im",
    )
    fd = ui.apply_filters(df, filters, numeric_cols=["opening_stock"])
    fd = fd.sort_values("item_name")
    ui.show_table(fd, key="im_grid")

with tab_add:
    with st.form("add_item", clear_on_submit=True):
        c1, c2 = st.columns(2)
        item_code = c1.text_input("Item Code")
        product_code = c2.text_input("Product Code")
        item_name = st.text_input("Item Name")
        c3, c4 = st.columns(2)
        uom = c3.text_input("UOM")
        opening_stock = c4.number_input("Opening Stock", min_value=0.0, value=0.0)
        c5, c6 = st.columns(2)
        group = c5.text_input("Group")
        sub_group = c6.text_input("Sub Group")
        submitted = st.form_submit_button("Add Item")
    if submitted:
        if not (item_code.strip() and product_code.strip() and item_name.strip() and uom.strip()):
            st.error("Item Code, Product Code, Item Name and UOM are required.")
        else:
            s = get_session()
            if s.query(ItemMaster).filter_by(item_code=item_code.strip()).first():
                st.error(f"Item code '{item_code}' already exists.")
            else:
                s.add(ItemMaster(
                    item_code=item_code.strip(),
                    product_code=product_code.strip(),
                    item_name=item_name.strip(),
                    uom=uom.strip(),
                    opening_stock=opening_stock,
                    grn_qty=0.0,
                    issued_qty=0.0,
                    group=group.strip() or None,
                    sub_group=sub_group.strip() or None,
                ))
                s.commit()
                st.success("Item added.")
            s.close()
            st.rerun()

with tab_edit:
    options = df["item_code"].tolist()
    sel = st.selectbox("Select Item Code", options, key="im_edit_sel")
    row = df[df["item_code"] == sel].iloc[0]
    with st.form("edit_item"):
        e_product = st.text_input("Product Code", value=row["product_code"] or "")
        e_name = st.text_input("Item Name", value=row["item_name"] or "")
        c1, c2 = st.columns(2)
        e_uom = c1.text_input("UOM", value=row["uom"] or "")
        e_open = c2.number_input("Opening Stock", value=float(row["opening_stock"] or 0.0))
        c3, c4 = st.columns(2)
        e_group = c3.text_input("Group", value=row["group"] or "")
        e_sub = c4.text_input("Sub Group", value=row["sub_group"] or "")
        st.caption("GRN Qty and Issued Qty are preserved and not editable here.")
        if st.form_submit_button("Save Changes"):
            s = get_session()
            obj = s.query(ItemMaster).filter_by(item_code=sel).first()
            obj.product_code = e_product.strip()
            obj.item_name = e_name.strip()
            obj.uom = e_uom.strip()
            obj.opening_stock = e_open
            obj.group = e_group.strip() or None
            obj.sub_group = e_sub.strip() or None
            s.commit()
            s.close()
            st.success("Item updated.")
            st.rerun()

with tab_delete:
    options_d = df["item_code"].tolist()
    sel_d = st.selectbox("Select Item Code to delete", options_d, key="im_del_sel")
    if st.button("Delete selected item", type="primary"):
        s = get_session()
        obj = s.query(ItemMaster).filter_by(item_code=sel_d).first()
        if obj:
            s.delete(obj)
            s.commit()
            st.success(f"Deleted item {sel_d}.")
            s.close()
            st.rerun()

st.download_button(
    "Export to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="item_master.csv",
    mime="text/csv",
)
