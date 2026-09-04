"""PRN (Purchase Requisition Note) — view/filter, create, edit and delete."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import PRN, PRNLine, BOMLine, ItemMaster, get_session
from utils import parse_job_number_range, to_float
import ui

st.set_page_config(page_title="PRN", layout="wide")
st.title("PRN (Purchase Requisition Note)")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

def load_df():
    Session = get_session()
    rows = (Session.query(PRNLine, PRN)
            .join(PRN, PRNLine.prn_id == PRN.id).all())
    df = pd.DataFrame([
        {**db.row_to_dict(pl), 'prn_no': prn.prn_no,
         'prn_date': (prn.prn_date.strftime('%Y-%m-%d') if prn.prn_date else None),
         'status': prn.status}
        for pl, prn in rows])
    Session.close()
    return df

df = load_df()
st.caption(f"Total PRN lines: {len(df):,}")

tab_view, tab_create, tab_delete = st.tabs(["View / Filter", "Create PRN", "Delete PRN"])

with tab_view:
    filters = ui.text_filters(
        ["prn_no", "bom_no", "bom_sr_no", "item_code", "product_code", "item_name",
         "uom", "job_no", "status", "required_qty", "prn_qty", "reserved_qty"], "prn"
    )
    fd = ui.apply_filters(df, filters, numeric_cols=["required_qty", "prn_qty", "reserved_qty"])
    fd = fd.sort_values("prn_date", ascending=False)
    ui.show_table(fd, key="prn_grid")

with tab_create:
    st.caption("Create a PRN. Optionally import its lines from BOM by Job No first, "
               "then the lines will be added below.")
    with st.form("create_prn"):
        c1, c2, c3 = st.columns(3)
        prn_no = c1.text_input("PRN No (blank = auto)")
        prn_date = c2.date_input("PRN Date")
        status = c3.selectbox("Status", ["Pending", "Approved", "Rejected"], index=0)
        job_no = st.text_input("Job No (header; range supported e.g. 2844-46)")
        job_group = st.text_input("Job Group (optional)")
        remarks = st.text_area("Remarks", height=60)
        import_from_bom = st.checkbox("Auto-fill lines from BOM for the given Job No")
        lines_raw = st.text_area(
            "Or paste lines: `ITEM-CODE\tPRODUCT-CODE\tITEM-NAME\tUOM\tREQUIRED-QTY\tPRN-QTY\tRESERVED-QTY`",
            height=120)
        submitted = st.form_submit_button("Create PRN")
    if submitted:
        s = get_session()
        final_prn_no = prn_no.strip() or f"PRN-{db.datetime.now().strftime('%Y%m%d%H%M%S')}"
        prn_obj = PRN(prn_no=final_prn_no, prn_date=prn_date, job_no=job_no.strip() or '',
                      job_group=job_group.strip() or None, status=status,
                      remarks=remarks.strip() or None)
        s.add(prn_obj)
        s.flush()

        lines = []
        if import_from_bom and job_no.strip():
            jobs = parse_job_number_range(job_no.strip())
            for jn in jobs:
                boms = s.query(BOMLine).filter(BOMLine.job_no == str(jn)).all()
                for bl in boms:
                    lines.append({
                        'bom_no': bl.bom_no, 'bom_sr_no': bl.bom_sr_no,
                        'item_code': bl.item_code, 'product_code': bl.product_code,
                        'item_name': bl.item_name, 'uom': bl.uom,
                        'required_qty': bl.quantity, 'prn_qty': bl.quantity,
                        'reserved_qty': 0.0,
                    })
        if lines_raw.strip():
            for line in lines_raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split('\t') if p.strip()]
                if len(parts) < 6:
                    st.error(f"Line needs at least 6 tab fields: {line}")
                    continue
                lines.append({
                    'bom_no': None, 'bom_sr_no': None,
                    'item_code': parts[0], 'product_code': parts[1],
                    'item_name': parts[2], 'uom': parts[3],
                    'required_qty': to_float(parts[4]), 'prn_qty': to_float(parts[5]),
                    'reserved_qty': to_float(parts[6]) if len(parts) > 6 else 0.0,
                })

        if not lines:
            st.warning("No lines were added to the PRN.")
        for ln in lines:
            # stock_qty = opening_stock - reserved_qty
            item = s.query(ItemMaster).filter_by(item_code=ln['item_code']).first()
            opening = item.opening_stock if item else 0.0
            stock_qty = (opening or 0.0) - ln['reserved_qty']
            s.add(PRNLine(prn_id=prn_obj.id, bom_no=ln['bom_no'], bom_sr_no=ln['bom_sr_no'],
                          item_code=ln['item_code'], product_code=ln['product_code'],
                          item_name=ln['item_name'], uom=ln['uom'],
                          job_no=job_no.strip() or None, required_qty=ln['required_qty'],
                          prn_qty=ln['prn_qty'], reserved_qty=ln['reserved_qty'],
                          stock_qty=stock_qty))
        s.commit()
        s.close()
        st.success(f"Created PRN {final_prn_no} with {len(lines)} line(s).")
        st.rerun()

with tab_delete:
    s = get_session()
    headers = s.query(PRN).all()
    opts = {f"{p.prn_no} | {p.prn_date} | job {p.job_no}": p.id for p in headers}
    s.close()
    if opts:
        sel = st.selectbox("Select PRN to delete", list(opts.keys()), key="prn_del")
        if st.button("Delete this PRN and its lines", type="primary"):
            s = get_session()
            p = s.query(PRN).get(opts[sel])
            if p:
                s.delete(p)
                s.commit()
                st.success(f"Deleted PRN {p.prn_no}.")
                s.close()
                st.rerun()
    else:
        st.info("No PRNs to delete.")

st.download_button(
    "Export PRN to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="prn.csv",
    mime="text/csv",
)
