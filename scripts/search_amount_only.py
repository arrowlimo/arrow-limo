#!/usr/bin/env python3
"""
Search banking_transactions for specific debit amounts in a date window (vendor-agnostic).
"""
import psycopg2
from datetime import date

AMOUNTS = [2061.00, 2061.19, 1935.70, 130.00, 130.30]
START = date(2018, 9, 1)
END = date(2019, 6, 30)

def main():
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()
    print(f"Scan {START}..{END} for debit amounts: {', '.join([f'{a:.2f}' for a in AMOUNTS])}")
    for amt in AMOUNTS:
        print(f"\nAmount ${amt:,.2f}")
        cur.execute("""
            SELECT transaction_id, transaction_date, description, debit_amount, vendor_extracted
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s AND %s
              AND ABS(COALESCE(debit_amount,0) - %s) < 0.01
            ORDER BY transaction_date
        """, (START, END, amt))
        rows = cur.fetchall()
        if not rows:
            print("  No matches")
        for r in rows:
            tid, tdate, desc, debit, vend = r
            print(f"  {tdate}  ID {tid}  debit ${debit or 0:.2f}  vendor={vend or ''}\n    {desc[:180]}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
