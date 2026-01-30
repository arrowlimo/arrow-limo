#!/usr/bin/env python3
"""
Search for payments to Woodridge Ford around Jan 2, 2019 for specific amounts.

Amounts to search: 2061.00, 1935.70, 130.00
Date window: Primary 2018-12-01 to 2019-02-28; fallback full 2019 if no hits.
Matches on vendor_extracted or description containing 'WOODRIDGE'.
"""

import os
from datetime import date
import psycopg2

AMOUNTS = [2061.00, 2061.19, 1935.70, 130.00]
PRIMARY_START = date(2018, 12, 1)
PRIMARY_END = date(2019, 2, 28)
FALLBACK_START = date(2019, 1, 1)
FALLBACK_END = date(2019, 12, 31)

DB_SETTINGS = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

QUERY = """
SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, vendor_extracted
FROM banking_transactions
WHERE transaction_date BETWEEN %s AND %s
  AND (
        UPPER(COALESCE(vendor_extracted,'') || ' ' || COALESCE(description,'')) LIKE '%%WOODRIDGE%%'
  )
  AND ABS(COALESCE(debit_amount,0) - %s) < 0.01
ORDER BY transaction_date
"""

FALLBACK_QUERY = """
SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, vendor_extracted
FROM banking_transactions
WHERE transaction_date BETWEEN %s AND %s
  AND ABS(COALESCE(debit_amount,0) - %s) < 0.01
ORDER BY transaction_date
"""

def search_window(cur, start, end, amount, require_vendor=True):
    cur.execute(QUERY if require_vendor else FALLBACK_QUERY, (start, end, amount))
    return cur.fetchall()


def main():
    with psycopg2.connect(**DB_SETTINGS) as conn:
        with conn.cursor() as cur:
            print("SEARCH: Woodridge Ford payments for amounts 2061.00, 1935.70, 130.00")
            print("Window: {} to {}".format(PRIMARY_START, PRIMARY_END))
            total_hits = 0
            for amt in AMOUNTS:
                print("\nAmount ${:,.2f}".format(amt))
                cur.execute(QUERY, (PRIMARY_START, PRIMARY_END, amt))
                rows = cur.fetchall()
                if rows:
                    total_hits += len(rows)
                    for r in rows:
                        tid, tdate, desc, debit, credit, vend = r
                        print(f"  {tdate}  ID {tid}  debit ${debit:,.2f}  vendor={vend or ''}")
                        print(f"    {desc[:180]}")
                else:
                    print("  No matches in primary window; trying fallback full-2019 vendor match...")
                    cur.execute(QUERY, (FALLBACK_START, FALLBACK_END, amt))
                    rows2 = cur.fetchall()
                    if rows2:
                        total_hits += len(rows2)
                        for r in rows2:
                            tid, tdate, desc, debit, credit, vend = r
                            print(f"  {tdate}  ID {tid}  debit ${debit:,.2f}  vendor={vend or ''}")
                            print(f"    {desc[:180]}")
                    else:
                        print("  No vendor matches in 2019; scanning 2019 for amount-only candidates...")
                        cur.execute(FALLBACK_QUERY, (FALLBACK_START, FALLBACK_END, amt))
                        rows3 = cur.fetchall()
                        if rows3:
                            total_hits += len(rows3)
                            for r in rows3:
                                tid, tdate, desc, debit, credit, vend = r
                                print(f"  {tdate}  ID {tid}  debit ${debit:,.2f}  vendor={vend or ''}")
                                print(f"    {desc[:180]}")
                        else:
                            print("  No matches found.")
            print(f"\nDone. Total candidate matches: {total_hits}")

if __name__ == '__main__':
    main()
