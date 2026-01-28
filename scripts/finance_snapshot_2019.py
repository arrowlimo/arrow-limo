#!/usr/bin/env python3
"""
Finance Snapshot for 2019

Outputs:
  - Console summary: totals, inflow/outflow/net, monthly breakdown
  - CSVs in reports/: snapshot_2019_monthly.csv, snapshot_2019_categories.csv, snapshot_2019_vendors.csv

Schema flexibility:
  - Supports receipts schemas with either (gross_amount, gst_amount) or legacy (expense with Epson convention)
  - Tries common column names for category/classification/subcategory
"""

import os
import psycopg2
from collections import defaultdict

DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'), 
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432'))
}

def fetch_columns(cur, table: str):
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    return {r[0] for r in cur.fetchall()}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cols = fetch_columns(cur, 'receipts')
    if not cols:
        print('[WARN] receipts table not found')
        return

    # Determine amount semantics
    has_gross = 'gross_amount' in cols
    has_gst = 'gst_amount' in cols or 'gst' in cols
    has_expense = 'expense' in cols
    # Determine category fields
    category_col = 'category' if 'category' in cols else ('classification' if 'classification' in cols else None)
    subcat_col = 'sub_classification' if 'sub_classification' in cols else None
    vendor_col = 'vendor_name' if 'vendor_name' in cols else None

    # Build select
    select_parts = ["receipt_date"]
    if vendor_col:
        select_parts.append(vendor_col)
    if category_col:
        select_parts.append(category_col)
    if subcat_col:
        select_parts.append(subcat_col)
    if has_gross:
        select_parts += ["gross_amount", ("gst_amount" if 'gst_amount' in cols else 'gst')]
    elif has_expense:
        select_parts.append("expense")
    else:
        print('[WARN] No recognizable amount columns in receipts')
        return

    sql = f"""
        SELECT {', '.join(select_parts)}
        FROM receipts
        WHERE receipt_date >= '2019-01-01' AND receipt_date < '2020-01-01'
          AND receipt_date IS NOT NULL
    """
    cur.execute(sql)
    rows = cur.fetchall()

    # Indices
    idx = {name: i for i, name in enumerate(select_parts)}

    total_inflow = 0.0
    total_outflow = 0.0
    monthly = defaultdict(lambda: {"inflow":0.0, "outflow":0.0})
    categories = defaultdict(float)
    vendors = defaultdict(float)

    for r in rows:
        date = r[idx['receipt_date']]
        cat = r[idx[category_col]] if category_col else None
        sub = r[idx[subcat_col]] if subcat_col else None
        vendor = r[idx[vendor_col]] if vendor_col else None

        if has_gross:
            amt = float(r[idx['gross_amount']] or 0)
        else:
            # Epson convention: expenses positive, revenue negative → flip to signed amount where outflows negative
            exp = float(r[idx['expense']] or 0)
            amt = -exp  # expense positive means outflow → negative

        ym = f"{date.year}-{date.month:02d}"

        if amt >= 0:
            total_inflow += amt
            monthly[ym]['inflow'] += amt
        else:
            total_outflow += -amt
            monthly[ym]['outflow'] += -amt

        key_cat = cat if not sub else f"{cat} / {sub}"
        if key_cat:
            categories[key_cat] += abs(amt)
        if vendor:
            vendors[vendor] += abs(amt)

    net = total_inflow - total_outflow

    print("=== Finance Snapshot: 2019 ===")
    print(f"Transactions: {len(rows):,}")
    print(f"Inflow (revenue-like): ${total_inflow:,.2f}")
    print(f"Outflow (expense-like): ${total_outflow:,.2f}")
    print(f"Net: ${net:,.2f}")
    print("\nMonthly totals (YYYY-MM):")
    for ym in sorted(monthly.keys()):
        m = monthly[ym]
        print(f"  {ym} | In: ${m['inflow']:,.2f} | Out: ${m['outflow']:,.2f} | Net: ${m['inflow']-m['outflow']:,.2f}")

    # Write CSVs
    os.makedirs('reports', exist_ok=True)
    import csv
    with open('reports/snapshot_2019_monthly.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['month','inflow','outflow','net'])
        for ym in sorted(monthly.keys()):
            m = monthly[ym]
            w.writerow([ym, m['inflow'], m['outflow'], m['inflow']-m['outflow']])
    with open('reports/snapshot_2019_categories.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['category','amount_abs'])
        for k, v in sorted(categories.items(), key=lambda kv: kv[1], reverse=True):
            w.writerow([k, v])
    with open('reports/snapshot_2019_vendors.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['vendor','amount_abs'])
        for k, v in sorted(vendors.items(), key=lambda kv: kv[1], reverse=True):
            w.writerow([k, v])

    print("\nCSV outputs:")
    print("  reports/snapshot_2019_monthly.csv")
    print("  reports/snapshot_2019_categories.csv")
    print("  reports/snapshot_2019_vendors.csv")

if __name__ == '__main__':
    main()
