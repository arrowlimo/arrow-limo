#!/usr/bin/env python3
"""
Find candidate transactions in May 2012 across all banking accounts for given amounts.
Reads l:\\limo\\reports\\screenshot_rows.csv and for any NOT_FOUND amounts searches any account
for exact amount match on either side within May 2012, printing candidates.
"""
import csv
import os
import psycopg2
from datetime import date
from decimal import Decimal

DB = dict(host=os.getenv('DB_HOST','localhost'), dbname=os.getenv('DB_NAME','almsdata'), user=os.getenv('DB_USER','postgres'), password=os.getenv('DB_PASSWORD','***REDACTED***'))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=str, default=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports', 'screenshot_rows.csv')))
    args = ap.parse_args()

    in_csv = args.csv
    if not os.path.exists(in_csv):
        print(f'Input not found: {in_csv}')
        return

    targets = []
    with open(in_csv, 'r', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            amt = Decimal(row['amount'])
            dt = date.fromisoformat(row['date'])
            targets.append((dt, amt, row.get('description','').strip()))

    conn = psycopg2.connect(**DB); cur = conn.cursor()
    print('Searching any account for exact amount matches (either side) in May 2012...')
    for dt, amt, desc in targets:
        if dt.month != 5 or dt.year != 2012:
            continue
        cur.execute(
            """
            SELECT account_number, transaction_id, transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_date BETWEEN '2012-05-01' AND '2012-05-31'
              AND ( (debit_amount > 0 AND ABS(debit_amount - %s) < 0.01)
                    OR (credit_amount > 0 AND ABS(credit_amount - %s) < 0.01) )
            ORDER BY transaction_date, account_number, transaction_id
            """,
            (amt, amt)
        )
        rows = cur.fetchall()
        print(f'Amount {amt:.2f} ({desc or ""}) → {len(rows)} candidates:')
        for a, tid, tdate, dsc, deb, cred in rows[:10]:
            print(f'  {tdate}  acct={a}  id={tid}  debit={deb} credit={cred}  desc={(dsc or "")[:80]}')
        if len(rows) > 10:
            print(f'  ... (+{len(rows)-10} more)')
        print()
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
