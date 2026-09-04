"""Job Master — view, add, edit and delete jobs."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import JobMaster, get_session
from utils import parse_job_number_range
import ui

st.set_page_config(page_title="Job Master", layout="wide")
st.title("Job Master")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()

Session = get_session()
df = pd.DataFrame(
    [db.row_to_dict(r) for r in Session.query(JobMaster).order_by(JobMaster.job_no).all()]
)
Session.close()

st.caption(f"Total jobs: {len(df):,}")

tab_view, tab_add, tab_edit, tab_delete = st.tabs(["View / Filter", "Add Jobs", "Edit Job", "Delete"])

with tab_view:
    filters = ui.text_filters(["job_no", "job_detail", "customer", "job_group"], "jm")
    fd = ui.apply_filters(df, filters)
    fd = fd.sort_values("job_no")
    ui.show_table(fd, key="jm_grid")

with tab_add:
    st.caption("Batch add: enter each job on its own line, or a range like 2844-46 to create one job per number.")
    st.caption("Format: JOB_NO<TAB>JOB_DETAIL<TAB>CUSTOMER  (paste from Excel works)")
    raw = st.text_area("Paste jobs", height=160)
    st.markdown("**OR allow a simple Job Group range:**")
    c1, c2 = st.columns(2)
    range_input = c1.text_input("Job Group range (e.g. 2844-46)")
    range_detail = c2.text_input("Common Job Detail", value="")
    if st.button("Add Jobs"):
        s = get_session()
        added = 0
        existing = 0
        errors = 0
        if range_input.strip():
            for jn in parse_job_number_range(range_input.strip()):
                jno = str(jn)
                if s.query(JobMaster).filter_by(job_no=jno).first():
                    existing += 1
                    continue
                s.add(JobMaster(job_no=jno, job_detail=range_detail.strip() or jno,
                                customer="", job_group=range_input.strip()))
                added += 1
        # Parse pasted lines
        if raw.strip():
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [p.strip() for p in line.split('\t') if p.strip()] or [p.strip() for p in line.split(',') if p.strip()]
                if len(parts) < 1:
                    errors += 1
                    continue
                jno = parts[0]
                detail = parts[1] if len(parts) > 1 else jno
                customer = parts[2] if len(parts) > 2 else ''
                if s.query(JobMaster).filter_by(job_no=jno).first():
                    existing += 1
                    continue
                s.add(JobMaster(job_no=jno, job_detail=detail, customer=customer))
                added += 1
        s.commit()
        s.close()
        st.success(f"Added {added} jobs, {existing} skipped (already exist), {errors} invalid lines.")
        st.rerun()

with tab_edit:
    options = df["job_no"].tolist()
    sel = st.selectbox("Select Job No", options, key="jm_edit_sel")
    row = df[df["job_no"] == sel].iloc[0]
    with st.form("edit_job"):
        e_detail = st.text_input("Job Detail", value=row["job_detail"] or "")
        e_customer = st.text_input("Customer", value=row["customer"] or "")
        e_group = st.text_input("Job Group", value=row["job_group"] or "")
        if st.form_submit_button("Save Changes"):
            s = get_session()
            obj = s.query(JobMaster).filter_by(job_no=sel).first()
            obj.job_detail = e_detail.strip()
            obj.customer = e_customer.strip()
            obj.job_group = e_group.strip() or None
            s.commit()
            s.close()
            st.success("Job updated.")
            st.rerun()

with tab_delete:
    options_d = df["job_no"].tolist()
    sel_d = st.selectbox("Select Job No to delete", options_d, key="jm_del_sel")
    if st.button("Delete selected job", type="primary"):
        s = get_session()
        obj = s.query(JobMaster).filter_by(job_no=sel_d).first()
        if obj:
            s.delete(obj)
            s.commit()
            st.success(f"Deleted job {sel_d}.")
            s.close()
            st.rerun()

st.download_button(
    "Export to CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="job_master.csv",
    mime="text/csv",
)
