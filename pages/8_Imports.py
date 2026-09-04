"""Imports — upload CSV/Excel files with the exact same formats as the Flask app.
All imported rows are written straight to the cloud Turso database."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

import db
from db import (ItemMaster, JobMaster, BOM, BOMLine, PRN, PRNLine, GRN, GRNLine,
                PMI, PMILine, get_session)
from utils import (clean_item_numeric_string, parse_job_number_range, parse_grn_date,
                   to_float)
import io

st.set_page_config(page_title="Imports", layout="wide")
st.title("Imports")
st.caption("Upload files in the same format used by the original desktop app. "
           "All rows are saved to the cloud database.")

if not st.session_state.get('db_ok', False):
    st.warning("Database connection failed.")
    st.stop()


def read_upload(uploaded_file, table_name):
    """Read an uploaded Excel/CSV into a DataFrame (CSV encoding auto-detected)."""
    if uploaded_file is None:
        return None
    name = uploaded_file.name.lower()
    if name.endswith('.xlsx') or name.endswith('.xls'):
        return pd.read_excel(uploaded_file)
    # CSV: try encodings + delimiters
    raw = uploaded_file.getvalue()
    for enc in ('utf-8', 'latin-1', 'cp1252', 'utf-16'):
        try:
            text = raw.decode(enc)
            for delim in (',', '\t', ';', '|'):
                try:
                    df = pd.read_csv(io.StringIO(text), delimiter=delim, encoding=enc)
                    if len(df.columns) >= 2:
                        df.columns = [str(c).strip() for c in df.columns]
                        return df
                except Exception:
                    continue
        except Exception:
            continue
    st.error(f"Could not read {uploaded_file.name}. Please use CSV/XLSX.")
    return None


def map_col(df, *keywords, excludes=()):
    """Return the first column whose (lowercased) name contains all keywords and none of excludes."""
    lk = {str(c).lower().strip(): c for c in df.columns}
    for colname, orig in lk.items():
        if all(k in colname for k in keywords) and not any(x in colname for x in excludes):
            return orig
    return None


def clean_sr(v):
    if v is None:
        return ''
    return clean_item_numeric_string(v)


# ----------------------------------------------------------------------
# Helpers for each import type
# ----------------------------------------------------------------------

def import_items_df(df):
    s = get_session()
    req = ['Item Code', 'Product Code', 'Item Name', 'UOM']
    col_map = {
        'item_code': map_col(df, 'item', 'code', excludes=['product']),
        'product_code': map_col(df, 'product', 'code'),
        'item_name': map_col(df, 'item', 'name'),
        'uom': map_col(df, 'uom'),
        'opening_stock': map_col(df, 'opening', 'stock'),
        'group': map_col(df, 'group', excludes=['sub']),
        'sub_group': map_col(df, 'sub', 'group'),
    }
    added = updated = skipped = 0
    for _, row in df.iterrows():
        ic = clean_item_numeric_string(row.get(col_map['item_code']))
        if not ic:
            skipped += 1
            continue
        existing = s.query(ItemMaster).filter_by(item_code=ic).first()
        vals = {
            'product_code': clean_item_numeric_string(row.get(col_map['product_code'])),
            'item_name': str(row.get(col_map['item_name']) or '').strip(),
            'uom': str(row.get(col_map['uom']) or '').strip(),
            'opening_stock': to_float(row.get(col_map['opening_stock'])),
            'group': row.get(col_map['group']),
            'sub_group': row.get(col_map['sub_group']),
        }
        if existing:
            existing.product_code = vals['product_code']
            existing.item_name = vals['item_name']
            existing.uom = vals['uom']
            existing.opening_stock = vals['opening_stock']
            existing.group = vals['group']
            existing.sub_group = vals['sub_group']
            updated += 1
        else:
            s.add(ItemMaster(item_code=ic, grn_qty=0.0, issued_qty=0.0, **vals))
            added += 1
    s.commit()
    s.close()
    return f"Items: {added} added, {updated} updated, {skipped} skipped (no code).", added, updated


def import_jobs_df(df):
    s = get_session()
    col_map = {
        'job_no': map_col(df, 'job', 'no', excludes=['group']),
        'job_detail': (map_col(df, 'job', 'detail') or map_col(df, 'detail')),
        'customer': map_col(df, 'customer'),
        'job_group': map_col(df, 'job', 'group'),
    }
    added = updated = skipped = 0
    for _, row in df.iterrows():
        jno = clean_item_numeric_string(row.get(col_map['job_no']))
        if not jno:
            skipped += 1
            continue
        detail = str(row.get(col_map['job_detail']) or '').strip() or jno
        customer = str(row.get(col_map['customer']) or '').strip()
        jg = row.get(col_map['job_group'])
        existing = s.query(JobMaster).filter_by(job_no=jno).first()
        if existing:
            existing.job_detail = detail
            existing.customer = customer
            existing.job_group = jg if jg is not None else existing.job_group
            updated += 1
        else:
            s.add(JobMaster(job_no=jno, job_detail=detail, customer=customer, job_group=jg))
            added += 1
    s.commit()
    s.close()
    return f"Jobs: {added} added, {updated} updated, {skipped} skipped.", added, updated


def import_bom_df(df):
    s = get_session()
    col_map = {
        'bom_sr_no': map_col(df, 'sr', 'no'),
        'job_no': map_col(df, 'job', 'no'),
        'item_code': map_col(df, 'item', 'code', excludes=['product']),
        'product_code': map_col(df, 'product', 'code'),
        'item_name': map_col(df, 'item', 'name'),
        'uom': map_col(df, 'uom'),
        'quantity': map_col(df, 'quantity') or map_col(df, 'qty'),
        'group': map_col(df, 'group', excludes=['sub']),
        'sub_group': map_col(df, 'sub', 'group'),
    }
    bom_no = f"IMP-{db.datetime.now().strftime('%Y%m%d%H%M%S')}"
    date = db.datetime.now().date()
    bom = BOM(bom_no=bom_no, job_no='IMPORTED', job_group='', date=date)
    s.add(bom)
    s.flush()
    count = 0
    for _, row in df.iterrows():
        items = col_map
        job_no = row.get(items['job_no'])
        quantity = to_float(row.get(items['quantity']))
        jobs = parse_job_number_range(job_no) if job_no else []
        if len(jobs) > 1:
            qty = round(quantity / len(jobs), 4)
            targets = jobs
        else:
            qty = quantity
            targets = jobs or [None]
        for jn in targets:
            s.add(BOMLine(
                bom_id=bom.id,
                bom_sr_no=clean_sr(row.get(items['bom_sr_no'])),
                job_no=str(jn) if jn else None,
                item_code=clean_item_numeric_string(row.get(items['item_code'])),
                product_code=clean_item_numeric_string(row.get(items['product_code'])),
                item_name=str(row.get(items['item_name']) or '').strip(),
                uom=str(row.get(items['uom']) or '').strip(),
                quantity=qty,
                group=row.get(items['group']),
                sub_group=row.get(items['sub_group']),
                revision='0',
                baseline_item_name=str(row.get(items['item_name']) or '').strip(),
                baseline_quantity=qty,
            ))
            count += 1
    s.commit()
    s.close()
    return f"BOM: {count} lines appended under BOM No {bom_no}.", 0, count


def import_prn_df(df):
    s = get_session()
    col_map = {
        'prn_no': map_col(df, 'prn', 'no', excludes=['date', 'qty']),
        'prn_date': map_col(df, 'prn', 'date'),
        'job_no': map_col(df, 'job', 'no', excludes=['group']),
        'job_group': map_col(df, 'job', 'group'),
        'status': map_col(df, 'status'),
        'remarks': map_col(df, 'remark'),
        'bom_no': map_col(df, 'bom', 'no', excludes=['sr']),
        'bom_sr_no': map_col(df, 'bom', 'sr'),
        'item_code': map_col(df, 'item', 'code', excludes=['product']),
        'product_code': map_col(df, 'product', 'code'),
        'item_name': map_col(df, 'item', 'name'),
        'uom': map_col(df, 'uom'),
        'required_qty': map_col(df, 'required', 'qty'),
        'prn_qty': map_col(df, 'prn', 'qty'),
        'reserved_qty': map_col(df, 'reserved', 'qty'),
    }
    prn_groups = {k: v for k, v in df.groupby(df[col_map['prn_no']])}
    added = updated_lines = 0
    for prn_no, group in prn_groups.items():
        first = group.iloc[0]
        pno = clean_item_numeric_string(first.get(col_map['prn_no']))
        if not pno:
            continue
        existing = s.query(PRN).filter_by(prn_no=pno).first()
        if existing:
            prn = existing
        else:
            prn = PRN(prn_no=pno, prn_date=parse_grn_date(first.get(col_map['prn_date'])),
                      job_no=clean_item_numeric_string(first.get(col_map['job_no'])),
                      job_group=first.get(col_map['job_group']),
                      status=str(first.get(col_map['status']) or 'Pending')[:20],
                      remarks=first.get(col_map['remarks']))
            s.add(prn)
            s.flush()
        for _, row in group.iterrows():
            ic = clean_item_numeric_string(row.get(col_map['item_code']))
            sr = clean_sr(row.get(col_map['bom_sr_no']))
            line = s.query(PRNLine).filter_by(prn_id=prn.id, item_code=ic, bom_sr_no=sr).first()
            vals = {
                'bom_no': row.get(col_map['bom_no']),
                'product_code': clean_item_numeric_string(row.get(col_map['product_code'])),
                'item_name': str(row.get(col_map['item_name']) or '').strip(),
                'uom': str(row.get(col_map['uom']) or '').strip(),
                'job_no': clean_item_numeric_string(row.get(col_map['job_no'])),
                'required_qty': to_float(row.get(col_map['required_qty'])),
                'prn_qty': to_float(row.get(col_map['prn_qty'])),
                'reserved_qty': to_float(row.get(col_map['reserved_qty'])),
            }
            if line:
                line.bom_no = vals['bom_no']
                line.product_code = vals['product_code']
                line.item_name = vals['item_name']
                line.uom = vals['uom']
                line.job_no = vals['job_no']
                line.required_qty = vals['required_qty']
                line.prn_qty = vals['prn_qty']
                line.reserved_qty = vals['reserved_qty']
            else:
                s.add(PRNLine(prn_id=prn.id, bom_sr_no=sr, stock_qty=0.0, **vals))
                added_lines += 1
        added += 1
    s.commit()
    s.close()
    return f"PRN: {added} PRN headers upserted, {added_lines} new lines.", added, added_lines


def import_grn_df(df, mode):
    s = get_session()
    if mode == 'replace':
        # children first
        s.query(GRNLine).delete()
        s.query(GRN).delete()
    col_map = {
        'grn_no': map_col(df, 'grn', 'no', excludes=['date']),
        'grn_date': map_col(df, 'grn', 'date'),
        'supplier_name': map_col(df, 'supplier'),
        'invoice_no': map_col(df, 'invoice', 'no', excludes=['date']),
        'invoice_date': map_col(df, 'invoice', 'date'),
        'remarks': map_col(df, 'remark'),
        'item_code': map_col(df, 'item', 'code', excludes=['product']),
        'product_code': map_col(df, 'product', 'code'),
        'item_name': map_col(df, 'item', 'name'),
        'uom': map_col(df, 'uom'),
        'received_qty': map_col(df, 'received', 'qty'),
        'date': map_col(df, 'date'),
        'po_number': map_col(df, 'po'),
        'job_no': map_col(df, 'job', 'no', excludes=['group']),
        'last_purchase_price': map_col(df, 'price'),
    }
    grn_groups = {k: v for k, v in df.groupby(df[col_map['grn_no']])}
    added = lines = 0
    for grn_no, group in grn_groups.items():
        first = group.iloc[0]
        gno = clean_item_numeric_string(first.get(col_map['grn_no'])) or \
            f"GRN-{db.datetime.now().strftime('%Y%m%d%H%M%S')}"
        existing = s.query(GRN).filter_by(grn_no=gno).first()
        gdate = parse_grn_date(first.get(col_map['grn_date']))
        if existing:
            grn = existing
        else:
            grn = GRN(grn_no=gno, grn_date=gdate,
                      supplier_name=first.get(col_map['supplier_name']),
                      invoice_no=first.get(col_map['invoice_no']),
                      invoice_date=parse_grn_date(first.get(col_map['invoice_date']) or None) or None,
                      remarks=first.get(col_map['remarks']))
            s.add(grn)
            s.flush()
            added += 1
        for _, row in group.iterrows():
            ic = clean_item_numeric_string(row.get(col_map['item_code']))
            received = to_float(row.get(col_map['received_qty']))
            job = row.get(col_map['job_no'])
            jobs = parse_job_number_range(job) if job else [None]
            for jn in jobs:
                qty = round(received / len(jobs), 4) if len(jobs) > 1 else received
                s.add(GRNLine(grn_id=grn.id, item_code=ic,
                              product_code=clean_item_numeric_string(row.get(col_map['product_code'])),
                              item_name=str(row.get(col_map['item_name']) or '').strip(),
                              uom=str(row.get(col_map['uom']) or '').strip(),
                              received_qty=qty,
                              date=gdate,
                              po_number=row.get(col_map['po_number']),
                              job_no=str(jn) if jn else None,
                              last_purchase_price=to_float(row.get(col_map['last_purchase_price']))))
                item = s.query(ItemMaster).filter_by(item_code=ic).first()
                if item:
                    item.grn_qty = (item.grn_qty or 0.0) + qty
                lines += 1
    s.commit()
    s.close()
    return f"GRN: {added} headers added, {lines} lines written (mode={mode}).", added, lines


def import_pmi_df(df):
    s = get_session()
    col_map = {
        'pmi_no': map_col(df, 'pmi', 'no', excludes=['date']),
        'pmi_date': map_col(df, 'pmi', 'date'),
        'supplier_name': map_col(df, 'supplier'),
        'invoice_no': map_col(df, 'invoice', 'no', excludes=['date']),
        'invoice_date': map_col(df, 'invoice', 'date'),
        'remarks': map_col(df, 'remark'),
        'item_code': map_col(df, 'item', 'code', excludes=['product']),
        'product_code': map_col(df, 'product', 'code'),
        'item_name': map_col(df, 'item', 'name'),
        'uom': map_col(df, 'uom'),
        'received_qty': map_col(df, 'received', 'qty'),
        'date': map_col(df, 'date'),
        'job_no': map_col(df, 'job', 'no', excludes=['group']),
    }
    groups = {k: v for k, v in df.groupby(df[col_map['pmi_no']])}
    added = lines = skipped = 0
    for pmi_no, group in groups.items():
        first = group.iloc[0]
        pno = clean_item_numeric_string(first.get(col_map['pmi_no']))
        if not pno:
            skipped += 1
            continue
        pdate = parse_grn_date(first.get(col_map['pmi_date']))
        existing = s.query(PMI).filter_by(pmi_no=pno).first()
        if existing:
            pmi = existing
        else:
            pmi = PMI(pmi_no=pno, pmi_date=pdate,
                      supplier_name=first.get(col_map['supplier_name']),
                      invoice_no=first.get(col_map['invoice_no']),
                      invoice_date=parse_grn_date(first.get(col_map['invoice_date']) or None) or None,
                      remarks=first.get(col_map['remarks']))
            s.add(pmi)
            s.flush()
            added += 1
        for _, row in group.iterrows():
            ic = clean_item_numeric_string(row.get(col_map['item_code']))
            pc = clean_item_numeric_string(row.get(col_map['product_code']))
            nm = str(row.get(col_map['item_name']) or '').strip()
            uom = str(row.get(col_map['uom']) or '').strip()
            if not (ic and pc and nm and uom):
                skipped += 1
                continue
            received = to_float(row.get(col_map['received_qty']))
            job = row.get(col_map['job_no'])
            jobs = parse_job_number_range(job) if job else [None]
            for jn in jobs:
                qty = round(received / len(jobs), 4) if len(jobs) > 1 else received
                s.add(PMILine(pmi_id=pmi.id, item_code=ic, product_code=pc, item_name=nm,
                              uom=uom, received_qty=qty, date=pdate,
                              job_no=str(jn) if jn else None))
                item = s.query(ItemMaster).filter_by(item_code=ic).first()
                if item:
                    item.grn_qty = (item.grn_qty or 0.0) + qty
                lines += 1
    s.commit()
    s.close()
    return f"PMI: {added} headers added, {lines} lines written, {skipped} skipped.", added, lines


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

option = st.selectbox("What are you importing?", [
    "Item Master (CSV)", "Job Master (Excel/CSV)", "BOM (Excel/CSV)",
    "PRN (CSV)", "GRN (CSV)", "PMI (CSV)",
])

uploaded = st.file_uploader(f"Choose the {option} file", type=["csv", "xlsx", "xls"])

if uploaded is not None:
    df = read_upload(uploaded, option)
    if df is not None:
        st.success(f"Read {len(df):,} rows — columns: {list(df.columns)}")
        mode = 'append'
        if option.startswith('GRN'):
            mode = st.radio("Import mode", ["append", "replace"], index=0,
                            help="replace deletes all existing GRN data first")
        if st.button("Import now", type="primary"):
            with st.spinner("Importing into the cloud database…"):
                try:
                    if option.startswith('Item'):
                        msg, a, u = import_items_df(df)
                    elif option.startswith('Job'):
                        msg, a, u = import_jobs_df(df)
                    elif option.startswith('BOM'):
                        msg, a, u = import_bom_df(df)
                    elif option.startswith('PRN'):
                        msg, a, u = import_prn_df(df)
                    elif option.startswith('GRN'):
                        msg, a, u = import_grn_df(df, mode)
                    else:
                        # PMI
                        msg, a, u = import_pmi_df(df)
                    st.success(msg)
                except Exception as e:
                    st.error(f"Import failed: {e}")