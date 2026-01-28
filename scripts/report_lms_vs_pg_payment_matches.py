#!/usr/bin/env python3
"""
Report LMS vs PostgreSQL Payment Matching Status
================================================

Goal (per user request):
1. Identify LMS payments that are matched to reserve numbers (all LMS payments have Reserve_No per completeness check).
2. Determine which almsdata (PostgreSQL) payments do NOT have a corresponding LMS payment.

Matching Logic:
- Primary key for LMS payment identity is LMS Payment.[Key] ("payment_key" concept)
- In PostgreSQL `payments.payment_key` holds the LMS [Key] when sourced from LMS; new integrated sources (Square, banking, etc.) may lack or use different formats.
- We'll extract all LMS payment keys + (Reserve_No, Amount) triples.
- We'll classify PostgreSQL payments into:
    A. Has LMS key match (payment_key in LMS key set)
    B. Has (reserve_number, amount) match to an LMS payment (fallback when key missing) 
    C. No LMS match by key nor reserve+amount => "extra in PG" (integrated / non-LMS)

Outputs:
- Summary counts
- Top samples of category C (unmatched PG payments) for inspection
- Optionally write CSV (use --csv path)

Safety: READ-ONLY. No writes.
"""
import os
import sys
import argparse
import csv
import psycopg2
import pyodbc
from collections import defaultdict

LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def get_lms_conn():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', help='Optional CSV output for unmatched PG payments')
    ap.add_argument('--limit', type=int, default=50, help='Sample size for printing unmatched')
    args = ap.parse_args()

    print('='*120)
    print('LMS vs PostgreSQL Payment Matching Report')
    print('='*120)

    # Connect
    try:
        lms_conn = get_lms_conn()
        pg_conn = get_pg_conn()
    except Exception as e:
        print(f'Connection failure: {e}')
        return 1
    lms_cur = lms_conn.cursor()
    pg_cur = pg_conn.cursor()

    # Pull LMS payments
    print('Loading LMS payments (Key, Reserve_No, Amount)...')
    lms_cur.execute('SELECT [Key], Reserve_No, Amount FROM Payment WHERE [Key] IS NOT NULL')
    lms_rows = lms_cur.fetchall()
    lms_keys = set()
    lms_by_reserve_amount = defaultdict(list)  # (reserve, amount) -> list[key]
    for key, reserve, amount in lms_rows:
        skey = str(key).strip()
        lms_keys.add(skey)
        # Normalize amount to cents integer to avoid float rounding diff
        cents = int(round(float(amount)*100)) if amount is not None else None
        lms_by_reserve_amount[(str(reserve).strip() if reserve is not None else None, cents)].append(skey)
    print(f'  LMS payment rows: {len(lms_rows):,}')
    print(f'  Distinct LMS keys: {len(lms_keys):,}')

    # Pull PG payments (limit to LMS historical window 2007-01-01 to cutoff 2025-01-01 unless extended later)
    print('Loading PostgreSQL payments...')
    pg_cur.execute('''
        SELECT payment_id, payment_date, amount, payment_key, reserve_number, account_number, payment_method, charter_id
        FROM payments
        WHERE payment_date >= '2007-01-01' AND payment_date < '2025-01-01'
    ''')
    pg_rows = pg_cur.fetchall()
    print(f'  PostgreSQL payments in window: {len(pg_rows):,}')

    # Classification
    matched_by_key = 0
    matched_by_res_amt_only = 0
    unmatched = []

    for pid, pdate, amount, pkey, reserve, account, method, charter_id in pg_rows:
        amt_cents = int(round(float(amount)*100)) if amount is not None else None
        key_match = False
        reserve_amt_match = False

        if pkey and pkey.strip() in lms_keys:
            matched_by_key += 1
            key_match = True
        else:
            # only attempt reserve+amount if we have both
            if reserve is not None and amount is not None:
                r_key = (str(reserve).strip(), amt_cents)
                if r_key in lms_by_reserve_amount:
                    matched_by_res_amt_only += 1
                    reserve_amt_match = True
        if not (key_match or reserve_amt_match):
            unmatched.append({
                'payment_id': pid,
                'payment_date': pdate,
                'amount': float(amount) if amount is not None else None,
                'payment_key': pkey,
                'reserve_number': reserve,
                'account_number': account,
                'payment_method': method,
                'charter_id': charter_id
            })

    total_pg = len(pg_rows)
    print('\nSummary:')
    print(f'  PG payments total (window): {total_pg:,}')
    print(f'    Matched by LMS payment_key: {matched_by_key:,} ({matched_by_key/total_pg*100:.2f}%)')
    print(f'    Matched by reserve+amount only: {matched_by_res_amt_only:,} ({matched_by_res_amt_only/total_pg*100:.2f}%)')
    unmatched_count = len(unmatched)
    print(f'    Unmatched in LMS: {unmatched_count:,} ({unmatched_count/total_pg*100:.2f}%)')

    # Sample unmatched
    limit = args.limit
    print('\nSample unmatched PostgreSQL payments (first {limit}):')
    for row in unmatched[:limit]:
        print(f"  ID {row['payment_id']}: {row['payment_date']} ${row['amount']:.2f} key={row['payment_key']} reserve={row['reserve_number']} method={row['payment_method']} account={row['account_number']} charter_id={row['charter_id']}")

    # Optional CSV
    if args.csv:
        fieldnames = list(unmatched[0].keys()) if unmatched else ['payment_id','payment_date','amount','payment_key','reserve_number','account_number','payment_method','charter_id']
        with open(args.csv,'w',newline='',encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for row in unmatched:
                w.writerow(row)
        print(f'\nCSV written: {args.csv} ({unmatched_count} rows)')

    # Close
    lms_cur.close(); lms_conn.close()
    pg_cur.close(); pg_conn.close()
    print('\nDone.')

if __name__ == '__main__':
    sys.exit(main())
