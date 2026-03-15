#!/usr/bin/env python3
"""
Analyze Drivers.xlsx columns and data completeness.

Outputs a text summary under reports/drivers_excel_column_audit_<DATE>.txt
"""
import os
import re
import sys
import datetime as dt

try:
    import pandas as pd
except Exception:
    print("pandas required. Install via: pip install pandas openpyxl")
    raise

ROOT = os.path.dirname(os.path.dirname(__file__))
EXCEL_PATH = os.path.join(ROOT, 'docs', 'DRIVERS', 'Drivers.xlsx')
REPORTS = os.path.join(ROOT, 'reports')
DATE = dt.date.today().isoformat()

NAME_COLS = ["name", "full name", "full_name", "employee", "driver", "driver name"]
NUM_COLS = ["driver #", "driver#", "driver no", "driver_no", "number", "employee_number", "code", "id"]
PHONE_COLS = ["phone", "cell", "cell phone", "cell_phone", "mobile", "phone number", "phone_number"]
EMAIL_COLS = ["email", "email address", "email_address"]
STATUS_COLS = ["status", "employment_status", "active"]
HIREDATE_COLS = ["hire date", "hire_date", "start date", "start_date"]

CANONICAL = {
    'full_name': NAME_COLS,
    'employee_number': NUM_COLS,
    'cell_phone': PHONE_COLS,
    'email': EMAIL_COLS,
    'employment_status': STATUS_COLS,
    'hire_date': HIREDATE_COLS,
}

WS_RE = re.compile(r"\s+")

def ncol(c: str) -> str:
    c = (c or '').strip().lower()
    c = c.replace('-', ' ').replace('_', ' ')
    c = WS_RE.sub(' ', c).strip()
    return c


def main(path: str = EXCEL_PATH):
    if not os.path.exists(path):
        print(f"Excel not found: {path}")
        sys.exit(1)

    df = pd.read_excel(path, sheet_name=0, dtype=str)
    orig_cols = list(df.columns)
    norm_cols = [ncol(c) for c in orig_cols]
    df.columns = norm_cols

    mapping = {}
    missing = []
    for key, candidates in CANONICAL.items():
        match = None
        for c in candidates:
            if c in df.columns:
                match = c
                break
        if match:
            mapping[key] = match
        else:
            missing.append(key)

    # Compute completeness
    stats = []
    for key, col in mapping.items():
        series = df[col]
        nonempty = int((series.fillna('').astype(str).str.strip() != '').sum())
        total = len(series)
        pct = (nonempty / total * 100.0) if total else 0.0
        stats.append((key, col, nonempty, total, pct))

    os.makedirs(REPORTS, exist_ok=True)
    out = os.path.join(REPORTS, f"drivers_excel_column_audit_{DATE}.txt")
    with open(out, 'w', encoding='utf-8') as f:
        f.write("Drivers.xlsx Column Audit\n")
        f.write(f"Source: {path}\n\n")
        f.write("Original Columns:\n")
        for c in orig_cols:
            f.write(f"  - {c}\n")
        f.write("\nNormalized Columns:\n")
        for c in norm_cols:
            f.write(f"  - {c}\n")
        f.write("\nCanonical Mapping (Excel → DB field):\n")
        for key, col in mapping.items():
            f.write(f"  - {key}: {col}\n")
        if missing:
            f.write("\nMissing Canonical Fields (not present in Excel):\n")
            for key in missing:
                f.write(f"  - {key}\n")
        else:
            f.write("\nMissing Canonical Fields: none\n")
        f.write("\nData Completeness:\n")
        for key, col, nonempty, total, pct in stats:
            f.write(f"  - {key} ({col}): {nonempty}/{total} non-empty ({pct:.1f}%)\n")
    print(f"Wrote audit: {out}")
    if missing:
        print("Missing canonical fields:")
        for key in missing:
            print(f"  - {key}")
    else:
        print("All canonical fields present.")
    print("Completeness summary:")
    for key, col, nonempty, total, pct in stats:
        print(f"  - {key}: {pct:.1f}% non-empty ({nonempty}/{total})")


if __name__ == '__main__':
    main()
