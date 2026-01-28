#!/usr/bin/env python3
import os
import psycopg2
from decimal import Decimal

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)

def search(cur, amount: Decimal, start_date=None, end_date=None):
    params = [amount]
    where = ["(ROUND(COALESCE(debit_amount,0)::numeric,2) = %s OR ROUND(COALESCE(credit_amount,0)::numeric,2) = %s)"]
    params.append(amount)
    if start_date:
        where.append("transaction_date >= %s")
        params.append(start_date)
    if end_date:
        where.append("transaction_date < %s")
        params.append(end_date)
    sql = f"""
        SELECT transaction_id, transaction_date, description,
               COALESCE(debit_amount,0) AS debit, COALESCE(credit_amount,0) AS credit,
               import_batch
        FROM banking_transactions
        WHERE {' AND '.join(where)}
        ORDER BY transaction_date, transaction_id
    """
    cur.execute(sql, params)
    return cur.fetchall()


def main():
    amt = Decimal(os.getenv('AMOUNT', '305.89'))
    jan = '2019-01-01'
    mar = '2019-03-01'  # end-exclusive

    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            print(f"Searching for amount ${amt} in Jan-Feb 2019...")
            rows = search(cur, amt, jan, mar)
            if not rows:
                print("No matches Jan-Feb 2019. Widening search to entire dataset...")
                rows = search(cur, amt)
            if not rows:
                print("No matches found for this amount.")
                return
            print(f"Found {len(rows)} match(es):")
            for tid, dt, desc, debit, credit, batch in rows:
                side = 'debit' if float(debit or 0) > 0 else 'credit'
                amt = debit if float(debit or 0) > 0 else credit
                print(f"  ID {tid} | {dt} | {side} ${amt:.2f} | {desc} | batch={batch}")

if __name__ == '__main__':
    main()
