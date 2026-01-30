#!/usr/bin/env python3
import os
import psycopg2

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)

with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        print("E-TRANSFERS Jan-Mar 2019 with debit between $295 and $315:")
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, debit_amount
            FROM banking_transactions
            WHERE transaction_date >= DATE '2019-01-01' AND transaction_date < DATE '2019-04-01'
              AND description ILIKE '%E-TRANSFER%'
              AND debit_amount BETWEEN 295 AND 315
            ORDER BY transaction_date
            """
        )
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  ID {r[0]} | {r[1]} | ${float(r[3] or 0):.2f} | {r[2]}")
        else:
            print("  None found in that range.")

        print("\nAny banking amounts ending in .89 (Jan-Mar 2019):")
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, 
                   COALESCE(debit_amount,0) AS debit, COALESCE(credit_amount,0) AS credit
            FROM banking_transactions
            WHERE transaction_date >= DATE '2019-01-01' AND transaction_date < DATE '2019-04-01'
              AND (
                 CAST(COALESCE(debit_amount,0) AS TEXT) LIKE '%.89' OR
                 CAST(COALESCE(credit_amount,0) AS TEXT) LIKE '%.89'
              )
            ORDER BY transaction_date
            """
        )
        rows2 = cur.fetchall()
        if rows2:
            for r in rows2:
                side = 'debit' if float(r[3] or 0) > 0 else 'credit'
                amt = r[3] if side=='debit' else r[4]
                print(f"  ID {r[0]} | {r[1]} | {side} ${amt:.2f} | {r[2]}")
        else:
            print("  No amounts ending in .89 in that window.")
