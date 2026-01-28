#!/usr/bin/env python3
"""Show all payments for a given reserve_number with simple aggregation.

Usage:
  python scripts/show_reserve_payments.py --reserve 014899

Outputs:
  Charter core financial fields
  Each payment row (id, date, amount, key)
  Totals: sum, count, e-transfer sum, non e-transfer sum

No writes performed.
"""

import os
import argparse
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')


def conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def main():
    ap = argparse.ArgumentParser(description='List payments for a reserve_number')
    ap.add_argument('--reserve','-r', required=True, help='Reserve number (e.g. 014899)')
    args = ap.parse_args()
    rv = args.reserve
    c = conn(); cur = c.cursor()
    cur.execute("SELECT charter_id, total_amount_due, paid_amount, balance, cancelled, status, charter_date FROM charters WHERE reserve_number=%s", (rv,))
    charter = cur.fetchone()
    if not charter:
        print(f"Reserve {rv} not found in charters table."); cur.close(); c.close(); return
    (charter_id, total_due, paid_amount, balance, cancelled, status, charter_date) = charter
    print(f"Charter reserve={rv} id={charter_id} date={charter_date} status={status} cancelled={cancelled}\n  total_due={total_due} paid_amount={paid_amount} balance={balance}")
    cur.execute("SELECT payment_id, amount, payment_date, payment_key FROM payments WHERE reserve_number=%s ORDER BY payment_date, payment_id", (rv,))
    rows = cur.fetchall()
    if not rows:
        print("No payments found.")
    etr_sum = 0.0; other_sum = 0.0
    print(f"\nPayments (count={len(rows)}):")
    for pid, amt, pdate, pkey in rows:
        flag = ''
        if pkey and pkey.startswith('ETR:'):
            etr_sum += float(amt); flag = 'ETR'
        else:
            other_sum += float(amt)
        print(f"  {pdate} id={pid} amount={amt:8.2f} key={pkey or ''} {flag}")
    print(f"\nTotals: sum={etr_sum+other_sum:.2f} e_transfer={etr_sum:.2f} other={other_sum:.2f}")
    # Cross-check difference vs charter paid_amount
    diff = (etr_sum + other_sum) - float(paid_amount or 0)
    if abs(diff) > 0.01:
        print(f"WARNING: Payment row sum {etr_sum+other_sum:.2f} differs from charter.paid_amount {paid_amount:.2f} by {diff:.2f}")
    cur.close(); c.close()


if __name__ == '__main__':
    main()
