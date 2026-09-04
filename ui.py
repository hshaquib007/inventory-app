"""
Reusable Streamlit UI helpers for lists, filters, add/edit forms and deletes.
Keeps the individual module pages short and consistent.
"""

import streamlit as st
import pandas as pd


def text_filters(columns, key_prefix):
    """Render a row of text filter boxes for the given columns.

    Returns a dict {column: value}.
    """
    values = {}
    cols = st.columns(len(columns))
    for i, col in enumerate(columns):
        v = cols[i].text_input(
            col.replace('_', ' ').title(),
            key=f"{key_prefix}_{col}",
        )
        values[col] = v.strip().lower()
    return values


def apply_filters(df, filters, numeric_cols=(), date_cols=()):
    """Apply the dict of text filters to a DataFrame (case-insensitive contains)."""
    out = df.copy()
    for col, val in filters.items():
        if not val:
            continue
        if col in out.columns:
            if col in numeric_cols:
                try:
                    num = float(val)
                    out = out[out[col].astype(float) == num]
                except ValueError:
                    pass
            else:
                out = out[out[col].astype(str).str.lower().str.contains(val, na=False)]
    return out


def show_table(df, height=460, key=None, use_container_width=True,
               hide_actions=False, column_config=None):
    """Render a dataframe with a column configuration (Streamlit data editor)."""
    return st.dataframe(
        df,
        height=height,
        use_container_width=use_container_width,
        hide_index=True,
        column_config=column_config,
    )


PAGE_SIZES = [50, 100, 250, 500]


def paginate(df, key):
    """Simple pagination controls. Returns the sliced page dataframe."""
    per_page = st.selectbox("Rows per page", PAGE_SIZES, index=0, key=f"{key}_pp")
    total = len(df)
    pages = max(1, (total + per_page - 1) // per_page)
    page = st.number_input(
        "Page", min_value=1, max_value=pages, value=1, key=f"{key}_page", step=1
    )
    start = (page - 1) * per_page
    st.caption(f"Showing {start + 1 if total else 0}–{min(start + per_page, total)} "
               f"of {total} records (page {page}/{pages})")
    return df.iloc[start:start + per_page]


def confirm_delete(label="Delete selected N/A"):
    """Return True if the user confirms a destructive action."""
    st.warning(label)
    left, right = st.columns(2)
    if left.button("Yes, delete", type="primary"):
        return True
    return False
