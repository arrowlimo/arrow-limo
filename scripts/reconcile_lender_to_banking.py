#!/usr/bin/env python3
"""
Reconcile lender_statement_transactions to banking receipts.

Logic:
  - Consider only lender rows with non-zero absolute amount.
  - For each lender row, find a receipts row where created_from_banking = true
    and ABS(receipts.expense) == ABS(lender.amount) within a ±2 day window.
  - Prefer the nearest date; if tie, pick first.
  - Report summary counts and dump CSVs of matched and unmatched for review.

Usage:
  python scripts/reconcile_lender_to_banking.py [--export-csv]
"""

import csv
import os
from datetime import timedelta

import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

QUERY = """
WITH lender AS (
  SELECT id, txn_date, description, amount, balance
  FROM lender_statement_transactions
  WHERE COALESCE(ABS(amount),0) > 0.001
),
receipts_banking AS (
  SELECT r_id, receipt_date, vendor_name, expense
  FROM (
    SELECT row_number() over () as r_id,
           receipt_date, vendor_name, expense
    FROM receipts
    WHERE created_from_banking = true
  ) t
),
matches AS (
  SELECT l.id as lender_id,
         l.txn_date as lender_date,
         l.description as lender_desc,
         l.amount as lender_amount,
         l.balance as lender_balance,
         r.r_id as receipt_row_id,
         r.receipt_date,
         r.vendor_name,
         r.expense,
         ABS(EXTRACT(EPOCH FROM (r.receipt_date::timestamp - l.txn_date::timestamp))) as date_diff_seconds
  FROM lender l
  JOIN receipts_banking r
    ON ABS(r.expense) = ABS(l.amount)
   AND r.receipt_date BETWEEN l.txn_date - INTERVAL '2 day' AND l.txn_date + INTERVAL '2 day'
)
SELECT DISTINCT ON (lender_id)
       lender_id, lender_date, lender_desc, lender_amount, lender_balance,
       receipt_row_id, receipt_date, vendor_name, expense
FROM matches
ORDER BY lender_id, date_diff_seconds ASC;
"""

def export_csv(path, rows, headers):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow([r.get(h, '') for h in headers])

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM lender_statement_transactions")
    total_lender = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM lender_statement_transactions WHERE COALESCE(ABS(amount),0) > 0.001")
    lender_nonzero = cur.fetchone()[0]

    cur.execute(QUERY)
    matched_rows = cur.fetchall()
    matched_by_id = {row[0]: row for row in matched_rows}

    cur.execute("""
      SELECT id, txn_date, description, amount, balance
      FROM lender_statement_transactions
      WHERE COALESCE(ABS(amount),0) > 0.001
    """)
    lender_rows = cur.fetchall()

    matched = []
    unmatched = []
    for id_, d, desc, amt, bal in lender_rows:
        m = matched_by_id.get(id_)
        if m:
            matched.append({
                'lender_id': id_,
                'lender_date': d,
                'lender_desc': desc,
                'lender_amount': float(amt),
                'lender_balance': float(bal) if bal is not None else None,
                'receipt_date': m[6],
                'vendor_name': m[7],
                'receipt_expense': float(m[8])
            })
        else:
            unmatched.append({
                'lender_id': id_,
                'lender_date': d,
                'lender_desc': desc,
                'lender_amount': float(amt),
                'lender_balance': float(bal) if bal is not None else None
            })

    print("=== LENDER RECON ===")
    print(f"Total lender rows: {total_lender}")
    print(f"Non-zero amount rows: {lender_nonzero}")
    print(f"Matched: {len(matched)}")
    print(f"Unmatched: {len(unmatched)}")

    # Export CSVs for review
    out_dir = 'reports'
    os.makedirs(out_dir, exist_ok=True)
    export_csv(os.path.join(out_dir, 'lender_matches.csv'), matched,
               ['lender_id','lender_date','lender_desc','lender_amount','lender_balance','receipt_date','vendor_name','receipt_expense'])
    export_csv(os.path.join(out_dir, 'lender_unmatched.csv'), unmatched,
               ['lender_id','lender_date','lender_desc','lender_amount','lender_balance'])
    print(f"Wrote reports/lender_matches.csv and reports/lender_unmatched.csv")

    conn.close()

if __name__ == '__main__':
    main()
