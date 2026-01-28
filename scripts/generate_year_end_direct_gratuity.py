#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Generate year-end direct gratuity statements (detail and summary).

Assumptions (per business decision Nov 9, 2025):
- Tips (cash, card/e-transfer) are treated as direct tips, excluded from payroll.
- We report direct tips per driver for a tax year using charter_date alignment.

Data sources:
- charters: cash_tip_amount, driver_gratuity_amount/driver_gratuity, driver_gratuity_percent + rate
- payments: square_tip linked to charters via charter_id or reserve_number

Outputs:
- reports/direct_gratuity_{year}_detail.csv
- reports/direct_gratuity_{year}_summary.csv (per driver per month + annual total)

Safe/defensive behaviors:
- Introspects table schemas and only uses columns that exist
- Gracefully handles NULLs and missing relationships
- Optional split of tips if a secondary driver is present
"""

import os
import sys
import csv
import argparse
import datetime as dt
from collections import defaultdict

try:
    import psycopg2
except Exception as e:
    print("ERROR: psycopg2 not available. Please install it in your environment.", file=sys.stderr)
    sys.exit(2)


def db_connect():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def get_columns(cur, table_name):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,)
    )
    return {r[0] for r in cur.fetchall()}


def fetch_employee_names(cur):
    cols = get_columns(cur, 'employees')
    name_col = 'full_name' if 'full_name' in cols else (
        'employee_name' if 'employee_name' in cols else None
    )
    if not name_col:
        return {}
    cur.execute(f"SELECT employee_id, {name_col} FROM employees")
    return {row[0]: row[1] for row in cur.fetchall()}


def fetch_charter_tip_rows(cur, year):
    start = dt.date(year, 1, 1)
    end = dt.date(year, 12, 31)

    ccols = get_columns(cur, 'charters')

    select_cols = ['charter_id', 'reserve_number', 'charter_date', 'assigned_driver_id']
    optional_cols = ['secondary_driver_id', 'cash_tip_amount', 'driver_gratuity_amount', 'driver_gratuity', 'driver_gratuity_percent', 'rate']
    for oc in optional_cols:
        if oc in ccols:
            select_cols.append(oc)

    cur.execute(
        f"""
        SELECT {', '.join(select_cols)}
        FROM charters
        WHERE charter_date >= %s AND charter_date <= %s
        """,
        (start, end)
    )

    rows = []
    col_idx = {col: i for i, col in enumerate(select_cols)}
    for rec in cur.fetchall():
        row = {col: rec[col_idx[col]] if col in col_idx else None for col in select_cols}

        # Normalize values
        charter_id = row.get('charter_id')
        reserve_number = row.get('reserve_number')
        charter_date = row.get('charter_date')
        driver_id = row.get('assigned_driver_id')
        secondary_driver_id = row.get('secondary_driver_id') if 'secondary_driver_id' in col_idx else None

        # Cash tip on charter
        cash_tip = row.get('cash_tip_amount') if 'cash_tip_amount' in col_idx else None
        if cash_tip and float(cash_tip) > 0:
            rows.append({
                'charter_id': charter_id,
                'reserve_number': reserve_number,
                'charter_date': charter_date,
                'driver_id': driver_id,
                'secondary_driver_id': secondary_driver_id,
                'source': 'cash_tip',
                'amount': float(cash_tip),
                'payment_date': None,
            })

        # Driver gratuity amount fields
        if 'driver_gratuity_amount' in col_idx:
            dga = row.get('driver_gratuity_amount')
            if dga and float(dga) > 0:
                rows.append({
                    'charter_id': charter_id,
                    'reserve_number': reserve_number,
                    'charter_date': charter_date,
                    'driver_id': driver_id,
                    'secondary_driver_id': secondary_driver_id,
                    'source': 'charter_gratuity_amount',
                    'amount': float(dga),
                    'payment_date': None,
                })
        elif 'driver_gratuity' in col_idx:
            dg = row.get('driver_gratuity')
            if dg and float(dg) > 0:
                rows.append({
                    'charter_id': charter_id,
                    'reserve_number': reserve_number,
                    'charter_date': charter_date,
                    'driver_id': driver_id,
                    'secondary_driver_id': secondary_driver_id,
                    'source': 'charter_gratuity',
                    'amount': float(dg),
                    'payment_date': None,
                })

        # Derive from percent × rate if no explicit amount
        if ('driver_gratuity_amount' not in col_idx) and ('driver_gratuity' not in col_idx):
            if 'driver_gratuity_percent' in col_idx and 'rate' in col_idx:
                pct = row.get('driver_gratuity_percent')
                rate = row.get('rate')
                try:
                    pct_val = float(pct) if pct is not None else 0.0
                    rate_val = float(rate) if rate is not None else 0.0
                    if pct_val > 0 and rate_val > 0:
                        # Accept both formats: 0-1 or 0-100
                        pct_norm = pct_val if pct_val <= 1.0 else pct_val / 100.0
                        derived = round(rate_val * pct_norm, 2)
                        if derived > 0:
                            rows.append({
                                'charter_id': charter_id,
                                'reserve_number': reserve_number,
                                'charter_date': charter_date,
                                'driver_id': driver_id,
                                'secondary_driver_id': secondary_driver_id,
                                'source': 'charter_gratuity_derived',
                                'amount': derived,
                                'payment_date': None,
                            })
                except Exception:
                    pass

    return rows


def fetch_square_tip_rows(cur, year):
    start = dt.date(year, 1, 1)
    end = dt.date(year, 12, 31)

    pcols = get_columns(cur, 'payments')
    if 'square_tip' not in pcols:
        return []

    # Build two branches: join by charter_id and by reserve_number
    # Note: We align tips by charter_date (charter year), not payment_date
    cur.execute(
        """
        SELECT p.square_tip, p.payment_date, c.charter_id, c.reserve_number, c.charter_date,
               c.assigned_driver_id, c.secondary_driver_id
        FROM payments p
        JOIN charters c ON p.charter_id = c.charter_id
        WHERE p.square_tip IS NOT NULL AND p.square_tip > 0
          AND c.charter_date >= %s AND c.charter_date <= %s
        UNION ALL
        SELECT p.square_tip, p.payment_date, c.charter_id, c.reserve_number, c.charter_date,
               c.assigned_driver_id, c.secondary_driver_id
        FROM payments p
        JOIN charters c ON p.reserve_number IS NULL AND p.reserve_number = c.reserve_number
        WHERE p.square_tip IS NOT NULL AND p.square_tip > 0
          AND c.charter_date >= %s AND c.charter_date <= %s
        """,
        (start, end, start, end)
    )

    rows = []
    for square_tip, payment_date, charter_id, reserve_number, charter_date, driver_id, secondary_driver_id in cur.fetchall():
        if square_tip and float(square_tip) > 0:
            rows.append({
                'charter_id': charter_id,
                'reserve_number': reserve_number,
                'charter_date': charter_date,
                'driver_id': driver_id,
                'secondary_driver_id': secondary_driver_id,
                'source': 'square_tip',
                'amount': float(square_tip),
                'payment_date': payment_date,
            })
    return rows


def split_if_secondary(entries, split_equal=False):
    if not split_equal:
        return entries
    out = []
    for e in entries:
        sid = e.get('secondary_driver_id')
        if sid and e.get('driver_id') and float(e.get('amount', 0)) > 0:
            half = round(float(e['amount']) / 2.0, 2)
            rem = round(float(e['amount']) - half, 2)  # preserve cents
            e1 = dict(e)
            e1['amount'] = half
            e2 = dict(e)
            e2['driver_id'] = sid
            e2['amount'] = rem
            out.extend([e1, e2])
        else:
            out.append(e)
    return out


def ensure_reports_dir():
    reports_dir = os.path.join(os.getcwd(), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    return reports_dir


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def write_outputs(year, detail_rows, emp_names):
    reports_dir = ensure_reports_dir()
    detail_path = os.path.join(reports_dir, f'direct_gratuity_{year}_detail.csv')
    summary_path = os.path.join(reports_dir, f'direct_gratuity_{year}_summary.csv')

    # Enrich rows with driver_name and month
    for r in detail_rows:
        r['driver_name'] = emp_names.get(r.get('driver_id'))
        cdate = r.get('charter_date')
        if isinstance(cdate, dt.datetime):
            cdate = cdate.date()
        r['month'] = month_key(cdate) if cdate else None

    # Write detail
    detail_cols = [
        'driver_id', 'driver_name', 'month', 'charter_date', 'payment_date',
        'reserve_number', 'charter_id', 'source', 'amount'
    ]
    with open(detail_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=detail_cols)
        w.writeheader()
        for r in sorted(detail_rows, key=lambda x: (x.get('driver_name') or '', x.get('charter_date') or dt.date(year,1,1))):
            out = {k: r.get(k) for k in detail_cols}
            w.writerow(out)

    # Build summary per driver per month
    monthly = defaultdict(float)
    annual = defaultdict(float)
    for r in detail_rows:
        drv = r.get('driver_id')
        m = r.get('month')
        amt = float(r.get('amount') or 0)
        if drv and m:
            monthly[(drv, m)] += amt
            annual[drv] += amt

    # Write summary
    months = [f"{year:04d}-{m:02d}" for m in range(1, 13)]
    summary_cols = ['driver_id', 'driver_name'] + months + ['annual_total']
    with open(summary_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=summary_cols)
        w.writeheader()

        driver_ids = sorted({drv for (drv, _m) in monthly.keys()} | set(annual.keys()))
        for drv in driver_ids:
            row = {
                'driver_id': drv,
                'driver_name': emp_names.get(drv),
                'annual_total': round(annual.get(drv, 0.0), 2)
            }
            for m in months:
                row[m] = round(monthly.get((drv, m), 0.0), 2)
            w.writerow(row)

    return detail_path, summary_path


def main():
    parser = argparse.ArgumentParser(description='Generate year-end direct gratuity statements (detail + summary).')
    parser.add_argument('--year', type=int, required=True, help='Tax year (e.g., 2012)')
    parser.add_argument('--split-equal-if-secondary', action='store_true', help='If a secondary driver is present, split tips equally.')
    args = parser.parse_args()

    year = args.year
    if year < 2000 or year > 2100:
        print('Invalid year provided.', file=sys.stderr)
        sys.exit(1)

    conn = None
    try:
        conn = db_connect()
        cur = conn.cursor()

        emp_names = fetch_employee_names(cur)

        charter_tip_rows = fetch_charter_tip_rows(cur, year)
        square_tip_rows = fetch_square_tip_rows(cur, year)

        all_rows = charter_tip_rows + square_tip_rows
        all_rows = split_if_secondary(all_rows, split_equal=args.split_equal_if_secondary)

        detail_path, summary_path = write_outputs(year, all_rows, emp_names)

        print(f"Wrote: {detail_path}")
        print(f"Wrote: {summary_path}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
