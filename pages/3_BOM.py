"""BOM (Bill of Materials) — view/filter, add, edit and delete BOM lines."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import BOM, BOMLine, get_session
from utils import parse_job_number_range, to_float
import ui

st.set_page_config(page_title="BOM", layout="wide")
st.title("BOM (Bill of Materials)")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

Session = get_session()

# BOM lines joined with parent BOM header (for bom_no + date)
rows = (Session.query(BOMLine, BOM)
        .join(BOM, BOMLine.bom_id == BOM.id)
        .all())
df = pd.DataFrame([
    {
        **db.row_to_dict(bom_line),
        'bom_date': (bom.date.strftime('%Y-%m-%d') if bom.date else None),
    }
    for bom_line, bom in rows
])
Session.close()

st.caption(f"Total BOM lines: {len(df):,}")

tab_view, tab_add, tab_delete = st.tabs(["View / Filter", "Add BOM Lines", "Delete BOM / Lines"])

with tab_view:
    filters = ui.text_filters(
        ["bom_no", "bom_sr_no", "job_no", "item_code", "product_code",
         "item_name", "uom", "quantity", "group", "sub_group", "revision"], "bom"
    )
    fd = ui.apply_filters(df, filters, numeric_cols=["quantity"])
    fd = fd.sort_values("bom_date", ascending=False)
    ui.show_table(fd, key="bom_grid")

with tab_add:
    st.caption("Add a new BOM with its lines. Use a job No range (e.g. 2844-46) "
               "to auto-split quantity across jobs.")
    with st.form("add_bom"):
        c1, c2, c3 = st.columns(3)
        bom_no = c1.text_input("BOM No (blank = auto IMP-<timestamp>)")
        job_no = c2.text_input("Job No / range")
        job_group = c3.text_input("Job Group (optional)")
        bom_date = st.date_input("BOM Date")
        st.markdown("**Lines** (one per row): `BOM-SR-NO\tITEM-CODE\tPRODUCT-CODE\tITEM-NAME\tUOM\tQUANTITY\tGROUP\tSUB-GROUP`")
        lines_raw = st.text_area("Paste lines", height=160)
        submitted = st.form_submit_button("Create BOM")
    if submitted:
        parsed_lines = []
        bad_line = None
        for line in lines_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            if len(parts) < 5:
                bad_line = line
                break
            parsed_lines.append({
                'bom_sr_no': parts[0],
                'item_code': parts[1],
                'product_code': parts[2],
                'item_name': parts[3],
                'uom': parts[4],
                'quantity': to_float(parts[5]) if len(parts) > 5 else 0.0,
                'group': parts[6] if len(parts) > 6 else None,
                'sub_group': parts[7] if len(parts) > 7 else None,
            })
        if bad_line:
            st.error(f"Line needs at least 5 tab-separated fields: {bad_line}")
        elif not parsed_lines:
            st.error("No valid lines provided.")
        else:
            final_bom_no = bom_no.strip() or f"IMP-{db.datetime.now().strftime('%Y%m%d%H%M%S')}"
            if job_no.strip() and '-' in job_no.strip():
                jobs = parse_job_number_range(job_no.strip())
            else:
                jobs = [job_no.strip()] if job_no.strip() else ['IMPORTED']
            s = get_session()
            created = 0
            for jn in jobs:
                bom = BOM(bom_no=final_bom_no, job_no=str(jn),
                          job_group=job_group.strip() or None, date=bom_date)
                s.add(bom)
                s.flush()
                for ld in parsed_lines:
                    qty = ld['quantity']
                    if len(jobs) > 1:
                        qty = round(qty / len(jobs), 4)
                    s.add(BOMLine(
                        bom_id=bom.id,
                        bom_sr_no=ld['bom_sr_no'],
                        job_no=str(jn),
                        item_code=ld['item_code'],
                        product_code=ld['product_code'],
                        item_name=ld['item_name'],
                        uom=ld['uom'],
                        quantity=qty,
                        group=ld['group'],
                        sub_group=ld['sub_group'],
                        revision='0',
                        baseline_item_name=ld['item_name'],
                        baseline_quantity=qty,
                    ))
                created += 1
            s.commit()
            s.close()
            st.success(f"Created {created} BOM header(s) with {len(parsed_lines)} line(s) each.")
            st.rerun()

with tab_delete:
    st.markdown("**Delete an entire BOM** (header + all its lines):")
    s = get_session()
    headers = s.query(BOM).all()
    opts = {f"{b.bom_no} | job {b.job_no} | {b.date}": b.id for b in headers}
    s.close()
    if opts:
        sel = st.selectbox("Select BOM to delete", list(opts.keys()), key="bom_del")
        if st.button("Delete this BOM and its lines", type="primary"):
            s = get_session()
            b = s.query(BOM).get(opts[sel])
            if b:
                s.delete(b)
                s.commit()
                st.success(f"Deleted BOM {b.bom_no}.")
                s.close()
                st.rerun()
    else:
        st.info("No BOMs to delete.")

st.download_button(
    "Export BOM to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="bom.csv",
    mime="text/csv",
)
