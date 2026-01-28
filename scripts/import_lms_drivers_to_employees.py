#!/usr/bin/env python3
"""
Import/sync LMS Driver records into employees table (dry-run by default).

- Source: L:\\limo\\backups\\lms.mdb, table assumed 'Driver' (auto-detects columns)
- Maps LMS fields to employees:
  * code/number -> employee_number (required)
  * name -> full_name
  * emp_type -> employee_category
  * hire_date -> hire_date
  * termdate -> termination_date
  * home_phone -> phone
  * work_phone -> cell_phone
  * email -> email
  * lic1_no -> driver_license_number
  * lic1_exp -> driver_license_expiry
  * lic2_no -> chauffeur_permit_number (if column exists), otherwise skipped with warning
  * lic2_exp -> chauffeur_permit_expiry
  * social_sec -> t4_sin
  * address fields -> street_address, city, province, postal_code, country
- Sets employment_status to 'inactive' for all rows by default (as requested).

Usage:
    python -X utf8 scripts/import_lms_drivers_to_employees.py --dry-run
    python -X utf8 scripts/import_lms_drivers_to_employees.py --write [--assign-missing-codes]

Notes:
- Requires pyodbc and Access ODBC driver.
- Produces CSV preview and audit in reports/.
"""

import os
import csv
import sys
import re
import argparse
from typing import Dict, Any, List, Tuple

import psycopg2
import psycopg2.extras as extras

try:
    import pyodbc  # type: ignore
except Exception:
    print("pyodbc is required. Install via pip install pyodbc and ensure 'Microsoft Access Driver (*.mdb, *.accdb)' is installed.")
    raise

ROOT = os.path.dirname(os.path.dirname(__file__))
MDB_PATH = os.path.join(ROOT, 'backups', 'lms.mdb')
REPORTS = os.path.join(ROOT, 'reports')

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

CANONICAL = {
    'code': ['driver', 'code', 'driver_no', 'driver number', 'driver_no_', 'driverid', 'driver_id', 'number', 'empno', 'emp_no'],
    'name': ['name', 'full name', 'driver name', 'fullname'],
    'emp_type': ['emp_type', 'type', 'employee_type'],
    'hire_date': ['hire_date', 'hire date', 'startdate', 'start_date', 'hdate'],
    'termdate': ['termdate', 'termination_date', 'enddate', 'end_date', 'tdate'],
    'home_phone': ['home_phone', 'home phone', 'phone', 'phone1'],
    'work_phone': ['work_phone', 'cell', 'cell_phone', 'mobile', 'phone2', 'work phone'],
    'email': ['email', 'email_address'],
    'lic1_no': ['lic1_no', 'license1', 'driver_license', 'dl_no'],
    'lic1_exp': ['lic1_exp', 'license1_exp', 'driver_license_exp'],
    'lic2_no': ['lic2_no', 'license2', 'badge_no', 'rd_badge', 'chauffeur_permit'],
    'lic2_exp': ['lic2_exp', 'license2_exp', 'badge_exp', 'rd_badge_exp', 'chauffeur_permit_exp'],
    'social_sec': ['social_sec', 'sin', 'ssn'],
    'address': ['address', 'street', 'street_address'],
    'city': ['city'],
    'province': ['province', 'state', 'prov'],
    'postal_code': ['postal_code', 'postal', 'zip'],
    'country': ['country'],
}

WS = re.compile(r"\s+")

def ncol(c: str) -> str:
    c = (c or '').strip().lower()
    c = c.replace('_', ' ').replace('-', ' ')
    return WS.sub(' ', c).strip()


def norm_name(s: str | None) -> str:
    s = (s or "").strip().lower()
    s = WS.sub(' ', s)
    return s


def connect_access(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Access DB not found: {path}")
    conn = pyodbc.connect(rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};")
    return conn


def get_driver_columns(ac_conn) -> List[str]:
    cur = ac_conn.cursor()
    # Try variations of table name
    for tbl in ["Driver", "Drivers", "EMPLOYEE", "Employees"]:
        try:
            cur.execute(f"SELECT * FROM {tbl} WHERE 1=0")
            cols = [ncol(d[0]) for d in cur.description]
            return [tbl] + cols
        except Exception:
            continue
    raise RuntimeError("Could not find Driver table (tried Driver/Drivers/EMPLOYEE/Employees)")


def pick(mapping_cols: List[str], candidates: List[str]) -> str | None:
    for c in candidates:
        if c in mapping_cols:
            return c
    return None


def read_lms_drivers(ac_conn) -> Tuple[str, List[Dict[str, Any]]]:
    tbl_cols = get_driver_columns(ac_conn)
    table = tbl_cols[0]
    cols = tbl_cols[1:]

    # Build dynamic select keeping original raw column names
    cur = ac_conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    raw_cols = [d[0] for d in cur.description]
    rows = []
    for r in cur.fetchall():
        rec = {}
        for i, val in enumerate(r):
            rec[ncol(raw_cols[i])] = val
        rows.append(rec)

    # Map to canonical keys
    records = []
    for rec in rows:
        def get(key):
            cand = CANONICAL[key]
            for c in cand:
                cc = ncol(c)
                if cc in rec and rec[cc] not in (None, ""):
                    return rec[cc]
            return None
        records.append({
            'code': get('code'),
            'name': get('name'),
            'emp_type': get('emp_type'),
            'hire_date': get('hire_date'),
            'termdate': get('termdate'),
            'home_phone': get('home_phone'),
            'work_phone': get('work_phone'),
            'email': get('email'),
            'lic1_no': get('lic1_no'),
            'lic1_exp': get('lic1_exp'),
            'lic2_no': get('lic2_no'),
            'lic2_exp': get('lic2_exp'),
            'social_sec': get('social_sec'),
            'address': get('address'),
            'city': get('city'),
            'province': get('province'),
            'postal_code': get('postal_code'),
            'country': get('country'),
        })
    return table, records


def get_columns(cur, table: str) -> set:
    cur.execute(
        """SELECT column_name FROM information_schema.columns 
            WHERE table_schema='public' AND table_name=%s""",
        (table,)
    )
    return {r[0] for r in cur.fetchall()}


def fetch_employees(cur) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    cols = get_columns(cur, 'employees')
    base = ['employee_id', 'employee_number', 'full_name']
    optional = [
        'phone', 'cell_phone', 'email', 'employee_category', 'hire_date', 'termination_date',
        'driver_license_number', 'driver_license_expiry', 'chauffeur_permit_expiry', 't4_sin',
        'street_address', 'city', 'province', 'postal_code', 'country'
    ]
    select_cols = base + [c for c in optional if c in cols]
    cur.execute(f"SELECT {', '.join(select_cols)} FROM employees")
    by_id: Dict[str, Dict[str, Any]] = {}
    by_num: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    for row in cur.fetchall():
        d = {select_cols[i]: row[i] for i in range(len(select_cols))}
        by_id[d['employee_id']] = d
        if d.get('employee_number'):
            by_num[str(d['employee_number']).strip().upper()] = d
        if d.get('full_name'):
            by_name[norm_name(str(d['full_name']))] = d
    return by_id, by_num, by_name


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """SELECT EXISTS (
               SELECT 1 FROM information_schema.columns
               WHERE table_schema='public' AND table_name=%s AND column_name=%s
           )""",
        (table, column),
    )
    return bool(cur.fetchone()[0])


def next_driver_code(cur) -> str:
    cur.execute("SELECT employee_number FROM employees WHERE employee_number ~ '^DR[0-9]+'")
    used = set()
    for r in cur.fetchall():
        try:
            used.add(int(re.sub(r'[^0-9]', '', r[0])))
        except Exception:
            pass
    n = 200
    while n in used:
        n += 1
    return f"DR{n}"


def plan(records: List[Dict[str, Any]], by_num, by_name, create_codes: bool, require_name_match: bool = True) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    planned: List[Dict[str, Any]] = []
    mismatches: List[Dict[str, Any]] = []
    for src in records:
        code = (str(src.get('code') or '').strip().upper()) or None
        name = (str(src.get('name') or '').strip()) or None
        target = None
        matched_by = None
        if code and code in by_num:
            target = by_num[code]
            matched_by = 'code'
        elif name and norm_name(name) in by_name:
            target = by_name[norm_name(name)]
            matched_by = 'name'
        if not target:
            # Skip unknown employees to avoid accidental creates
            continue
        # If matched by code, verify names when possible
        if require_name_match and matched_by == 'code':
            db_name = target.get('full_name')
            if db_name and name and norm_name(db_name) != norm_name(name):
                mismatches.append({
                    'employee_id': target.get('employee_id'),
                    'db_name': db_name,
                    'lms_name': name,
                    'employee_number': target.get('employee_number'),
                    'lms_code': code,
                })
                # Skip updating due to mismatch ONLY if require_name_match is True
                # (name mismatch still logged in CSV for review)
                continue
        changes = {}
        # Required employee_number
        if not target.get('employee_number'):
            if code:
                changes['employee_number'] = code
            elif create_codes:
                changes['employee_number'] = '<AUTO>'
        # Name (do not overwrite if exists)
        if not target.get('full_name') and name:
            changes['full_name'] = name
        # Category
        if not target.get('employee_category') and src.get('emp_type'):
            changes['employee_category'] = src['emp_type']
        # Dates
        if not target.get('hire_date') and src.get('hire_date'):
            changes['hire_date'] = src['hire_date']
        if not target.get('termination_date') and src.get('termdate'):
            changes['termination_date'] = src['termdate']
        # Contact
        if not target.get('phone') and src.get('home_phone'):
            changes['phone'] = src['home_phone']
        if not target.get('cell_phone') and src.get('work_phone'):
            changes['cell_phone'] = src['work_phone']
        if not target.get('email') and src.get('email'):
            changes['email'] = src['email']
        # Licenses
        if not target.get('driver_license_number') and src.get('lic1_no'):
            changes['driver_license_number'] = src['lic1_no']
        if not target.get('driver_license_expiry') and src.get('lic1_exp'):
            changes['driver_license_expiry'] = src['lic1_exp']
        if not target.get('chauffeur_permit_expiry') and src.get('lic2_exp'):
            changes['chauffeur_permit_expiry'] = src['lic2_exp']
        # SIN
        if not target.get('t4_sin') and src.get('social_sec'):
            changes['t4_sin'] = src['social_sec']
        # Address
        if not target.get('street_address') and src.get('address'):
            changes['street_address'] = src['address']
        if not target.get('city') and src.get('city'):
            changes['city'] = src['city']
        if not target.get('province') and src.get('province'):
            changes['province'] = src['province']
        if not target.get('postal_code') and src.get('postal_code'):
            changes['postal_code'] = src['postal_code']
        if not target.get('country') and src.get('country'):
            changes['country'] = src['country']
        # Employment status handled uniformly at write-time per user request
        if changes:
            planned.append({'employee_id': target['employee_id'], 'full_name': target.get('full_name'), 'planned': changes, 'lms_code': code, 'matched_by': matched_by})
    return planned, mismatches


def write_csv(path: str, headers: List[str], rows: List[List[Any]]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mdb', default=MDB_PATH)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--assign-missing-codes', action='store_true')
    ap.add_argument('--allow-name-mismatch', action='store_true', help='If set, updates proceed even if LMS name differs from DB when matching by code')
    ap.add_argument('--all-inactive', action='store_true', default=True, help='Set employment_status=inactive for all updated rows')
    args = ap.parse_args()

    ac = connect_access(args.mdb)
    table, records = read_lms_drivers(ac)
    print(f"Read {len(records)} LMS driver rows from table {table}")

    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            by_id, by_num, by_name = fetch_employees(cur)

    planned, mismatches = plan(records, by_num, by_name, create_codes=args.assign_missing_codes, require_name_match=not args.allow_name_mismatch)
    print(f"Planned updates for {len(planned)} employees")
    if mismatches:
        print(f"Name mismatches skipped: {len(mismatches)} (see reports/lms_driver_name_mismatches.csv)")

    preview = []
    for p in planned:
        c = p['planned']
        preview.append([p['employee_id'], p['full_name'], p['lms_code'], c.get('employee_number',''), c.get('email',''), c.get('phone',''), c.get('cell_phone',''), c.get('driver_license_number',''), c.get('driver_license_expiry',''), c.get('chauffeur_permit_expiry',''), c.get('t4_sin',''), c.get('hire_date',''), c.get('termination_date','')])
    write_csv(os.path.join(REPORTS, 'lms_drivers_planned_updates.csv'),
              ['employee_id','full_name','lms_code','employee_number','email','phone','cell_phone','driver_license_number','driver_license_expiry','chauffeur_permit_expiry','t4_sin','hire_date','termination_date'],
              preview)

    if mismatches:
        write_csv(os.path.join(REPORTS, 'lms_driver_name_mismatches.csv'),
                  ['employee_id','employee_number','db_name','lms_name','lms_code'],
                  [[m['employee_id'], m.get('employee_number',''), m['db_name'], m['lms_name'], m['lms_code']] for m in mismatches])

    if not args.write:
        print("Dry-run complete. See reports/lms_drivers_planned_updates.csv")
        return

    applied = 0
    audit = []
    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            has_permit_number = column_exists(cur, 'employees', 'chauffeur_permit_number')
            emp_cols = get_columns(cur, 'employees')
            for p in planned:
                emp_id = p['employee_id']
                changes = {k: v for k, v in dict(p['planned']).items() if k in emp_cols}
                if changes.get('employee_number') == '<AUTO>' and args.assign_missing_codes:
                    changes['employee_number'] = next_driver_code(cur)
                sets = []
                vals = []
                for k, v in changes.items():
                    sets.append(f"{k}=%s")
                    vals.append(v)
                if args.all_inactive:
                    sets.append("employment_status='inactive'")
                if not sets:
                    continue
                vals.append(emp_id)
                sql = f"UPDATE employees SET {', '.join(sets)} WHERE employee_id=%s"
                cur.execute(sql, vals)
                applied += cur.rowcount or 0
                audit.append([emp_id, p['full_name'], changes.get('employee_number',''), changes.get('email',''), changes.get('driver_license_number',''), changes.get('driver_license_expiry',''), changes.get('chauffeur_permit_expiry',''), changes.get('t4_sin','')])
            conn.commit()
    write_csv(os.path.join(REPORTS, 'lms_drivers_applied_updates.csv'),
              ['employee_id','full_name','employee_number','email','driver_license_number','driver_license_expiry','chauffeur_permit_expiry','t4_sin'],
              audit)
    print(f"Applied {applied} updates. Audit written.")

if __name__ == '__main__':
    main()
