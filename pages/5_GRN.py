"""GRN (Goods Receipt Note) — view/filter, create, delete (updates stock)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import GRN, GRNLine, ItemMaster, get_session
from utils import parse_job_number_range, to_float, parse_date_value
import ui

st.set_page_config(page_title="GRN", layout="wide")
st.title("GRN (Goods Receipt Note)")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

def load_df():
    Session = get_session()
    rows = (Session.query(GRNLine, GRN).join(GRN, GRNLine.grn_id == GRN.id).all())
    df = pd.DataFrame([
        {**db.row_to_dict(gl), 'grn_no': g.grn_no,
         'grn_date': (g.grn_date.strftime('%Y-%m-%d') if g.grn_date else None),
         'supplier_name': g.supplier_name}
        for gl, g in rows])
    Session.close()
    return df

df = load_df()
st.caption(f"Total GRN lines: {len(df):,}")

tab_view, tab_create, tab_delete = st.tabs(["View / Filter", "Create GRN", "Delete GRN"])

with tab_view:
    filters = ui.text_filters(
        ["grn_no", "item_code", "product_code", "item_name", "uom", "received_qty",
         "date", "po_number", "job_no", "last_purchase_price", "supplier_name"], "grn"
    )
    fd = ui.apply_filters(df, filters, numeric_cols=["received_qty", "last_purchase_price"])
    fd = fd.sort_values("grn_date", ascending=False)
    ui.show_table(fd, key="grn_grid")

with tab_create:
    st.caption("Create a GRN with lines. Received quantities increase Item Master GRN Qty.")
    with st.form("create_grn"):
        c1, c2, c3 = st.columns(3)
        grn_no = c1.text_input("GRN No (blank = auto)")
        grn_date = c2.date_input("GRN Date")
        supplier = c3.text_input("Supplier")
        c4, c5 = st.columns(2)
        inv_no = c4.text_input("Invoice No")
        inv_date = c5.date_input("Invoice Date", value=None)
        remarks = st.text_area("Remarks", height=50)
        lines_raw = st.text_area(
            "Lines: `ITEM-CODE\tPRODUCT-CODE\tITEM-NAME\tUOM\tRECEIVED-QTY\tPO-NO\tJOB-NO\tPRICE`",
            height=120)
        submitted = st.form_submit_button("Create GRN")
    if submitted:
        s = get_session()
        final_grn_no = grn_no.strip() or f"GRN-{db.datetime.now().strftime('%Y%m%d%H%M%S')}"
        grn_obj = GRN(grn_no=final_grn_no, grn_date=grn_date, supplier_name=supplier.strip() or None,
                      invoice_no=inv_no.strip() or None,
                      invoice_date=inv_date or None, remarks=remarks.strip() or None)
        s.add(grn_obj)
        s.flush()
        count = 0
        for line in lines_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            if len(parts) < 5:
                st.error(f"Line needs at least 5 tab fields: {line}")
                continue
            item_code, product_code, item_name, uom = parts[0:4]
            received_qty = to_float(parts[4])
            po_no = parts[5] if len(parts) > 5 else None
            job_no = parts[6] if len(parts) > 6 else None
            price = to_float(parts[7]) if len(parts) > 7 else 0.0
            jobs = parse_job_number_range(job_no) if job_no else [None]
            for jn in jobs:
                qty = round(received_qty / len(jobs), 4) if len(jobs) > 1 else received_qty
                s.add(GRNLine(grn_id=grn_obj.id, item_code=item_code,
                              product_code=product_code, item_name=item_name, uom=uom,
                              received_qty=qty, date=grn_date, po_number=po_no,
                              job_no=str(jn) if jn else None, last_purchase_price=price))
                item = s.query(ItemMaster).filter_by(item_code=item_code).first()
                if item:
                    item.grn_qty = (item.grn_qty or 0.0) + qty
                    if price:
                        item.last_purchase_price = price
                count += 1
        s.commit()
        s.close()
        st.success(f"Created GRN {final_grn_no} with {count} line(s).")
        st.rerun()

with tab_delete:
    s = get_session()
    headers = s.query(GRN).all()
    opts = {f"{g.grn_no} | {g.grn_date} | {g.supplier_name or ''}": g.id for g in headers}
    s.close()
    if opts:
        sel = st.selectbox("Select GRN to delete", list(opts.keys()), key="grn_del")
        if st.button("Delete this GRN and its lines (reverts stock)", type="primary"):
            s = get_session()
            g = s.query(GRN).get(opts[sel])
            if g:
                for gl in g.lines:
                    item = s.query(ItemMaster).filter_by(item_code=gl.item_code).first()
                    if item:
                        item.grn_qty = max(0.0, (item.grn_qty or 0.0) - gl.received_qty)
                s.delete(g)
                s.commit()
                st.success(f"Deleted GRN {g.grn_no} and reverted stock.")
                s.close()
                st.rerun()
    else:
        st.info("No GRNs to delete.")

st.download_button(
    "Export GRN to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="grn.csv",
    mime="text/csv",
)
