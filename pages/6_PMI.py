"""PMI (Purchase Material Issue) — view/filter, create and delete."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import PMI, PMILine, BOMLine, ItemMaster, get_session
from utils import parse_job_number_range, to_float
import ui

st.set_page_config(page_title="PMI", layout="wide")
st.title("PMI (Purchase Material Issue)")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

def load_df():
    Session = get_session()
    rows = (Session.query(PMILine, PMI).join(PMI, PMILine.pmi_id == PMI.id).all())
    out = []
    for pl, p in rows:
        d = db.row_to_dict(pl)
        # Look up BOM qty
        if pl.job_no:
            bl = Session.query(BOMLine).filter(
                BOMLine.item_code == pl.item_code, BOMLine.job_no == pl.job_no).first()
            d['bom_qty'] = bl.quantity if bl else 0.0
        else:
            d['bom_qty'] = 0.0
        d['pmi_no'] = p.pmi_no
        d['pmi_date'] = (p.pmi_date.strftime('%Y-%m-%d') if p.pmi_date else None)
        out.append(d)
    Session.close()
    return pd.DataFrame(out)

df = load_df()
st.caption(f"Total PMI lines: {len(df):,}")

tab_view, tab_create, tab_delete = st.tabs(["View / Filter", "Create PMI", "Delete PMI"])

with tab_view:
    filters = ui.text_filters(
        ["pmi_no", "item_code", "product_code", "item_name", "uom", "received_qty",
         "date", "job_no", "bom_qty"], "pmi"
    )
    fd = ui.apply_filters(df, filters, numeric_cols=["received_qty", "bom_qty"])
    fd = fd.sort_values("pmi_date", ascending=False)
    ui.show_table(fd, key="pmi_grid")

with tab_create:
    st.caption("Create a PMI with lines. Received/issued quantities affect Item Master GRN Qty.")
    with st.form("create_pmi"):
        c1, c2 = st.columns(2)
        pmi_no = c1.text_input("PMI No (blank = auto)")
        pmi_date = c2.date_input("PMI Date")
        supplier = st.text_input("Supplier")
        remarks = st.text_area("Remarks", height=50)
        lines_raw = st.text_area(
            "Lines: `ITEM-CODE\tPRODUCT-CODE\tITEM-NAME\tUOM\tRECEIVED-QTY\tJOB-NO`",
            height=120)
        submitted = st.form_submit_button("Create PMI")
    if submitted:
        s = get_session()
        final_pmi_no = pmi_no.strip() or f"PMI-{db.datetime.now().strftime('%Y%m%d%H%M%S')}"
        pmi_obj = PMI(pmi_no=final_pmi_no, pmi_date=pmi_date,
                      supplier_name=supplier.strip() or None, remarks=remarks.strip() or None)
        s.add(pmi_obj)
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
            job_no = parts[5] if len(parts) > 5 else None
            jobs = parse_job_number_range(job_no) if job_no else [None]
            for jn in jobs:
                qty = round(received_qty / len(jobs), 4) if len(jobs) > 1 else received_qty
                s.add(PMILine(pmi_id=pmi_obj.id, item_code=item_code,
                              product_code=product_code, item_name=item_name, uom=uom,
                              received_qty=qty, date=pmi_date,
                              job_no=str(jn) if jn else None))
                item = s.query(ItemMaster).filter_by(item_code=item_code).first()
                if item:
                    item.grn_qty = (item.grn_qty or 0.0) + qty
                count += 1
        s.commit()
        s.close()
        st.success(f"Created PMI {final_pmi_no} with {count} line(s).")
        st.rerun()

with tab_delete:
    s = get_session()
    headers = s.query(PMI).all()
    opts = {f"{p.pmi_no} | {p.pmi_date}": p.id for p in headers}
    s.close()
    if opts:
        sel = st.selectbox("Select PMI to delete", list(opts.keys()), key="pmi_del")
        if st.button("Delete this PMI and its lines (reverts stock)", type="primary"):
            s = get_session()
            p = s.query(PMI).get(opts[sel])
            if p:
                for pl in p.lines:
                    item = s.query(ItemMaster).filter_by(item_code=pl.item_code).first()
                    if item:
                        item.grn_qty = max(0.0, (item.grn_qty or 0.0) - pl.received_qty)
                s.delete(p)
                s.commit()
                st.success(f"Deleted PMI {p.pmi_no} and reverted stock.")
                s.close()
                st.rerun()
    else:
        st.info("No PMIs to delete.")

st.download_button(
    "Export PMI to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="pmi.csv",
    mime="text/csv",
)
