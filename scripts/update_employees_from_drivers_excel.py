#!/usr/bin/env python3
"""
Update employees from Drivers.xlsx (dry-run by default).

- Reads L:\\limo\\docs\\DRIVERS\\Drivers.xlsx (first sheet by default)
- Flexible column mapping (Name, Driver #, Phone, Email, Status, Hire Date)
- Matches existing employees by employee_number (preferred) then by normalized full_name
- Fills null/blank fields only by default (employee_number, cell_phone/phone, email, employment_status, hire_date)
- Optional --assign-missing-codes to generate unique driver codes (DR###) when none provided
- Outputs CSV reports under reports/

Usage:
    python -X utf8 scripts/update_employees_from_drivers_excel.py --dry-run
    python -X utf8 scripts/update_employees_from_drivers_excel.py --write --assign-missing-codes

Environment:
    Uses DB_* env vars as documented in copilot-instructions.md
"""

import os
import re
import csv
import sys
import argparse
import datetime as dt
from typing import Dict, Any, List, Tuple

import psycopg2
import psycopg2.extras as extras

try:
    import pandas as pd
except Exception as e:
    print("pandas is required to read Excel. Install via pip install pandas openpyxl")
    raise

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

ROOT = os.path.dirname(os.path.dirname(__file__))
REPORTS = os.path.join(ROOT, "reports")
DEFAULT_XLSX = os.path.join(ROOT, "docs", "DRIVERS", "Drivers.xlsx")
DATE = dt.date.today().isoformat()

NAME_COLS = ["name", "full name", "full_name", "employee", "driver", "driver name"]
NUM_COLS = ["driver #", "driver#", "driver no", "driver_no", "number", "employee_number", "code", "id"]
PHONE_COLS = ["phone", "cell", "cell phone", "cell_phone", "mobile", "phone number", "phone_number"]
EMAIL_COLS = ["email", "email address", "email_address"]
STATUS_COLS = ["status", "employment_status", "active"]
HIREDATE_COLS = ["hire date", "hire_date", "start date", "start_date"]

WHITESPACE = re.compile(r"\s+")


def norm_col(c: str) -> str:
    c = (c or "").strip().lower()
    c = c.replace("-", " ").replace("_", " ")
    c = WHITESPACE.sub(" ", c).strip()
    return c


def norm_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = WHITESPACE.sub(" ", s)
    return s


def coalesce(*vals):
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        return v
    return None


def read_excel(path: str) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, dtype=str)
    cols = [norm_col(c) for c in df.columns]
    df.columns = cols

    def pick(row, candidates):
        for c in candidates:
            if c in row and str(row[c]).strip() != "":
                return str(row[c]).strip()
        return None

    records = []
    for _, r in df.iterrows():
        rr = r.to_dict()
        name = pick(rr, NAME_COLS)
        if not name:
            continue
        number = pick(rr, NUM_COLS)
        phone = pick(rr, PHONE_COLS)
        email = pick(rr, EMAIL_COLS)
        status = pick(rr, STATUS_COLS)
        hire_date = pick(rr, HIREDATE_COLS)
        records.append({
            "full_name": name,
            "employee_number": number,
            "cell_phone": phone,
            "email": email,
            "employment_status": status,
            "hire_date": hire_date,
        })
    return records


def write_csv(path: str, headers: List[str], rows: List[List[Any]]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def fetch_employees(cur) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    cur.execute(
        """
        SELECT employee_id, employee_number, full_name, cell_phone, email, employment_status, hire_date, is_chauffeur
        FROM employees
        """
    )
    by_id = {}
    by_key = {}
    for row in cur.fetchall():
        d = dict(row=row, employee_id=row[0], employee_number=row[1], full_name=row[2],
                 cell_phone=row[3], email=row[4], employment_status=row[5], hire_date=row[6], is_chauffeur=row[7])
        by_id[row[0]] = d
        if row[1]:
            by_key[f"num::{row[1].strip().upper()}"] = d
        if row[2]:
            by_key[f"name::{norm_name(row[2])}"] = d
    return by_id, by_key


def next_driver_code(cur) -> str:
    # Generate next DR### code avoiding collisions. Start at 200 if none.
    cur.execute("""
        SELECT employee_number FROM employees WHERE employee_number ~ '^DR[0-9]+'
    """)
    used = set()
    for r in cur.fetchall():
        try:
            used.add(int(re.sub(r'[^0-9]', '', r[0])))
        except Exception:
            continue
    n = 200
    while n in used:
        n += 1
    return f"DR{n}"


def plan_updates(excel_rows, by_key, assign_missing_codes: bool) -> List[Dict[str, Any]]:
    planned = []
    for rec in excel_rows:
        key = None
        target = None
        if rec.get("employee_number"):
            key = f"num::{rec['employee_number'].strip().upper()}"
            target = by_key.get(key)
        if target is None:
            key = f"name::{norm_name(rec.get('full_name', ''))}"
            target = by_key.get(key)
        if target is None:
            # No match in DB; skip for safety
            continue
        changes = {}
        # Only fill blanks
        if (not target.get("employee_number")) and rec.get("employee_number"):
            changes["employee_number"] = rec["employee_number"].strip()
        if (not target.get("cell_phone")) and rec.get("cell_phone"):
            changes["cell_phone"] = rec["cell_phone"]
        if (not target.get("email")) and rec.get("email"):
            changes["email"] = rec["email"]
        if (not target.get("employment_status")) and rec.get("employment_status"):
            s = rec["employment_status"].strip().lower()
            if s in {"active", "inactive", "on_leave", "on leave"}:
                changes["employment_status"] = "on_leave" if s in {"on leave"} else s
        if (not target.get("hire_date")) and rec.get("hire_date"):
            changes["hire_date"] = rec["hire_date"]
        if (not target.get("is_chauffeur")):
            changes["is_chauffeur"] = True
        # Ensure required employee_number
        if "employee_number" not in changes and not target.get("employee_number") and assign_missing_codes:
            changes["employee_number"] = "<AUTO>"  # placeholder, resolved at write-time
        if changes:
            planned.append({
                "employee_id": target["employee_id"],
                "full_name": target["full_name"],
                "planned": changes,
            })
    return planned


def apply_updates(conn, planned: List[Dict[str, Any]], assign_missing_codes: bool) -> Tuple[int, List[List[Any]]]:
    applied = 0
    audit_rows: List[List[Any]] = []
    with conn.cursor(cursor_factory=extras.DictCursor) as cur:
        for item in planned:
            emp_id = item["employee_id"]
            changes = dict(item["planned"])  # copy
            # Resolve auto code if needed
            if changes.get("employee_number") == "<AUTO>" and assign_missing_codes:
                changes["employee_number"] = next_driver_code(cur)
            # Build SQL dynamically
            sets = []
            vals = []
            for k, v in changes.items():
                sets.append(f"{k} = %s")
                vals.append(v)
            if not sets:
                continue
            vals.append(emp_id)
            sql = f"UPDATE employees SET {', '.join(sets)} WHERE employee_id = %s"
            cur.execute(sql, vals)
            applied += cur.rowcount or 0
            audit_rows.append([emp_id, item["full_name"], changes.get("employee_number", ""), changes.get("cell_phone", ""), changes.get("email", ""), changes.get("employment_status", ""), changes.get("hire_date", ""), changes.get("is_chauffeur", "")])
        conn.commit()
    return applied, audit_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", default=DEFAULT_XLSX, help="Path to Drivers.xlsx")
    ap.add_argument("--write", action="store_true", help="Apply updates (default is dry-run)")
    ap.add_argument("--assign-missing-codes", action="store_true", help="Generate DR### codes when employee_number blank in DB and Excel")
    args = ap.parse_args()

    if not os.path.exists(args.excel):
        print(f"Excel not found: {args.excel}")
        sys.exit(1)

    excel_rows = read_excel(args.excel)
    print(f"Read {len(excel_rows)} rows from Excel")

    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            by_id, by_key = fetch_employees(cur)
    
    planned = plan_updates(excel_rows, by_key, assign_missing_codes=args.assign_missing_codes)
    print(f"Planned updates for {len(planned)} employees")

    # Reports
    os.makedirs(REPORTS, exist_ok=True)
    preview_rows = []
    for p in planned:
        c = p["planned"]
        preview_rows.append([p["employee_id"], p["full_name"], c.get("employee_number", ""), c.get("cell_phone", ""), c.get("email", ""), c.get("employment_status", ""), c.get("hire_date", ""), c.get("is_chauffeur", "")])
    write_csv(os.path.join(REPORTS, f"drivers_excel_planned_updates_{DATE}.csv"),
              ["employee_id", "full_name", "employee_number", "cell_phone", "email", "employment_status", "hire_date", "is_chauffeur"],
              preview_rows)

    if not args.write:
        print("Dry-run complete. See reports/drivers_excel_planned_updates_*.csv")
        return

    with psycopg2.connect(**PG) as conn:
        applied, audit_rows = apply_updates(conn, planned, assign_missing_codes=args.assign_missing_codes)
        write_csv(os.path.join(REPORTS, f"drivers_excel_applied_updates_{DATE}.csv"),
                  ["employee_id", "full_name", "employee_number", "cell_phone", "email", "employment_status", "hire_date", "is_chauffeur"],
                  audit_rows)
        print(f"Applied {applied} row updates. Audit written to reports/.")


if __name__ == "__main__":
    main()
