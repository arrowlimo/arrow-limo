#!/usr/bin/env python3
"""
Driver Pay Name → Employee ID mapping scaffold.

- Creates a mapping table `driver_name_employee_map` if it doesn't exist.
- Scans `staging_driver_pay` for distinct driver_name values.
- Generates confident suggestions by matching against `employees` using:
  1) Exact normalized full_name match
  2) Reversed name match ("Last, First" ↔ "First Last")
  3) Optional driver_id ↔ employee_number numeric match (if plausible)
- Inserts suggestions as rows (status='suggested').
- Prints coverage stats and writes optional CSV exports of ambiguous/unmatched.

Usage:
  python -X utf8 scripts/driver_pay_name_mapping.py [--out reports/driver_pay_mapping]

Notes:
- No updates to core tables. Safe to run repeatedly; uses idempotent UPSERT by normalized_name.
- Keep writes confined to mapping table only.
"""

import os
import csv
import argparse
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def normalize_name(s: str) -> str:
    if not s:
        return ''
    s = s.strip()
    # unify separators and punctuation
    s = re.sub(r'[\s,;:_\-\.]+' , ' ', s)
    s = s.lower().strip()
    return s


def reverse_if_comma_style(s: str) -> str:
    # Handle "Last, First" → "First Last"
    if ',' in s:
        parts = [p.strip() for p in s.split(',') if p.strip()]
        if len(parts) >= 2:
            return f"{parts[1]} {parts[0]}".strip()
    return s


def ensure_mapping_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS driver_name_employee_map (
            id SERIAL PRIMARY KEY,
            source_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            candidate_employee_id INTEGER,
            candidate_employee_name TEXT,
            candidate_method TEXT,
            confidence NUMERIC(5,4),
            status TEXT DEFAULT 'suggested', -- suggested|approved|rejected
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def fetch_employee_index(cur):
    # Build normalized indices for employees
    cur.execute(
        """
        SELECT employee_id, COALESCE(full_name, '') AS full_name,
               COALESCE(first_name,'') AS first_name,
               COALESCE(last_name,'') AS last_name,
               COALESCE(employee_number,'') AS employee_number
        FROM employees
        """
    )
    rows = cur.fetchall()

    by_full = {}
    by_reversed = {}
    by_empnum = {}

    for r in rows:
        eid = r['employee_id']
        full = normalize_name(r['full_name'])
        if full:
            by_full.setdefault(full, []).append((eid, r['full_name']))
        rev = normalize_name(f"{r['last_name']} {r['first_name']}")
        if rev:
            by_reversed.setdefault(rev, []).append((eid, r['full_name']))
        empnum = str(r['employee_number']).strip() if r['employee_number'] is not None else ''
        if empnum:
            by_empnum.setdefault(empnum, []).append((eid, r['full_name']))

    return by_full, by_reversed, by_empnum


def upsert_mapping(cur, source_name, normalized_name, candidate_employee_id, candidate_employee_name, method, confidence, status='suggested', notes=None):
    cur.execute(
        """
        INSERT INTO driver_name_employee_map
            (source_name, normalized_name, candidate_employee_id, candidate_employee_name, candidate_method, confidence, status, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (normalized_name)
        DO UPDATE SET
            source_name = EXCLUDED.source_name,
            candidate_employee_id = EXCLUDED.candidate_employee_id,
            candidate_employee_name = EXCLUDED.candidate_employee_name,
            candidate_method = EXCLUDED.candidate_method,
            confidence = EXCLUDED.confidence,
            -- do not override status if already approved/rejected
            notes = EXCLUDED.notes
        """,
        (source_name, normalized_name, candidate_employee_id, candidate_employee_name, method, confidence, status, notes)
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=None, help='Output prefix for CSV exports (e.g., reports/driver_pay_mapping)')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    ensure_mapping_table(cur)

    # Load distinct names from staging
    cur.execute(
        """
        SELECT DISTINCT TRIM(COALESCE(driver_name, '')) AS driver_name
        FROM staging_driver_pay
        WHERE TRIM(COALESCE(driver_name, '')) <> ''
        """
    )
    names = [row['driver_name'] for row in cur.fetchall()]

    by_full, by_reversed, by_empnum = fetch_employee_index(cur)

    suggestions = []
    ambiguous = []
    unmatched = []

    for raw in names:
        norm = normalize_name(raw)
        if not norm:
            continue

        # Try direct match
        cand = by_full.get(norm, [])
        method = 'full_name_exact'
        confidence = 0.98

        # Try reversed match if no/ambiguous
        if not cand or len(cand) != 1:
            rev_try = normalize_name(reverse_if_comma_style(raw))
            if rev_try and rev_try != norm:
                cand = by_full.get(rev_try, [])
                method = 'reversed_name_exact'
                confidence = 0.96 if len(cand) == 1 else 0.0

        # Potential numeric mapping: if raw looks like an ID seen in empnum
        if (not cand or len(cand) != 1) and raw.isdigit() and raw in by_empnum:
            cand = by_empnum.get(raw, [])
            method = 'employee_number_match'
            confidence = 0.99 if len(cand) == 1 else 0.0

        if len(cand) == 1:
            eid, ename = cand[0]
            suggestions.append((raw, norm, eid, ename, method, confidence))
            upsert_mapping(cur, raw, norm, eid, ename, method, confidence, status='suggested', notes=None)
        elif len(cand) > 1:
            ambiguous.append((raw, norm, cand))
            # Insert with no candidate to mark as pending
            upsert_mapping(cur, raw, norm, None, None, 'ambiguous', 0.0, status='suggested', notes=f"{len(cand)} candidates")
        else:
            unmatched.append((raw, norm))
            upsert_mapping(cur, raw, norm, None, None, 'unmatched', 0.0, status='suggested', notes=None)

    conn.commit()

    total = len(names)
    print('='*80)
    print('DRIVER PAY NAME MAPPING')
    print('='*80)
    print(f"Distinct names scanned: {total}")
    print(f"Confident suggestions:  {len(suggestions)}")
    print(f"Ambiguous:              {len(ambiguous)}")
    print(f"Unmatched:              {len(unmatched)}")

    # Optional CSVs
    if args.out:
        base = args.out
        os.makedirs(os.path.dirname(base), exist_ok=True)

        with open(base + '_suggestions.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['source_name','normalized_name','employee_id','employee_name','method','confidence'])
            for row in suggestions:
                w.writerow(row)
        with open(base + '_ambiguous.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['source_name','normalized_name','candidates'])
            for raw, norm, cands in ambiguous:
                w.writerow([raw, norm, '; '.join([f"{eid}:{ename}" for eid, ename in cands])])
        with open(base + '_unmatched.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['source_name','normalized_name'])
            for raw, norm in unmatched:
                w.writerow([raw, norm])
        print(f"\nCSV exports written with prefix: {base}_*.csv")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
