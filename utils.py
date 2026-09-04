"""
Shared helper functions ported from the Flask app so the Streamlit app
behaves identically (job-range splitting, date parsing, numeric cleaning).
"""

import re
from datetime import datetime, date


def clean_item_numeric_string(value):
    """Strip a value and remove a trailing '.0' (e.g. '1234.0' -> '1234')."""
    if value is None:
        return ''
    s = str(value).strip()
    return re.sub(r'\.0$', '', s)


def clean_job_numeric_string(value):
    return clean_item_numeric_string(value)


def parse_job_number_range(job_no_str):
    """
    Parse job number range with shorthand notation support.
    - '2844-46'   -> [2844, 2845, 2846]
    - '2844-2846' -> [2844, 2845, 2846]
    - '2844'      -> [2844]
    - None        -> []
    """
    if not job_no_str:
        return []

    job_no_str = str(job_no_str).strip()

    if '-' not in job_no_str:
        try:
            return [int(job_no_str)]
        except ValueError:
            return [job_no_str]

    try:
        parts = job_no_str.split('-')
        if len(parts) != 2:
            return [job_no_str]

        start_str = parts[0].strip()
        end_str = parts[1].strip()

        start = int(start_str)
        end = int(end_str)

        # Shorthand notation (e.g. '2844-46' where '46' means '2846')
        if len(end_str) < len(start_str):
            prefix = start_str[:len(start_str) - len(end_str)]
            end = int(prefix + end_str)

        if start > end:
            return [job_no_str]

        return list(range(start, end + 1))
    except ValueError:
        return [job_no_str]


def parse_grn_date(val, default=None):
    """Parse a date string across the common formats the Flask app supports."""
    if val is None or (isinstance(val, str) and val.strip() == ''):
        return default if default is not None else date.today()

    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    s = str(val).strip()
    # Normalize '.' separators to '-' then try formats
    formats = [
        '%d-%m-%y', '%d-%m-%Y', '%d/%m/%y', '%d/%m/%Y',
        '%Y-%m-%d', '%d.%m.%y', '%d.%m.%Y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return default if default is not None else date.today()


def parse_date_value(val, default=None):
    """Parse a date that could be already a date, datetime, or ISO string."""
    if val is None or (isinstance(val, str) and val.strip() == ''):
        return default
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return default


def to_float(value, default=0.0):
    try:
        if value is None or value == '':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=None):
    try:
        if value is None or value == '':
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default
