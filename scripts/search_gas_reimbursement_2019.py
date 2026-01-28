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

AMT = Decimal('305.89')
START = '2018-12-01'
END = '2019-04-01'  # end-exclusive
TOL = Decimal('0.50')

with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        print("Searching email_financial_events for ~$305.89 (Dec 2018 - Mar 2019)...")
        cur.execute(
            """
            SELECT id, email_date, from_email, subject, amount, entity, banking_transaction_id
            FROM email_financial_events
            WHERE email_date >= %s AND email_date < %s
              AND CAST(amount AS numeric) BETWEEN %s AND %s
            ORDER BY email_date
            """,
            (START, END, AMT - TOL, AMT + TOL)
        )
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  EMAIL  ID {r[0]} | {r[1]} | ${r[4]} | {r[2]} | {r[3]} | entity={r[5]} | bank_id={r[6]}")
        else:
            print("  No email events found in range for that amount window.")

        print("\nSearching banking_transactions for ~$305.89 (Dec 2018 - Mar 2019)...")
        cur.execute(
            """
            SELECT transaction_id, transaction_date, description,
                   COALESCE(debit_amount,0) AS debit, COALESCE(credit_amount,0) AS credit
            FROM banking_transactions
            WHERE transaction_date >= %s AND transaction_date < %s
              AND (
                 (COALESCE(debit_amount,0)::numeric BETWEEN %s AND %s) OR
                 (COALESCE(credit_amount,0)::numeric BETWEEN %s AND %s)
              )
            ORDER BY transaction_date, transaction_id
            """,
            (START, END, AMT - TOL, AMT + TOL, AMT - TOL, AMT + TOL)
        )
        rows = cur.fetchall()
        if rows:
            for r in rows:
                side = 'debit' if float(r[3] or 0) > 0 else 'credit'
                amt = r[3] if side=='debit' else r[4]
                print(f"  BANK   ID {r[0]} | {r[1]} | {side} ${amt:.2f} | {r[2]}")
        else:
            print("  No banking matches in that window; expanding to 2019 full year...")
            cur.execute(
                """
                SELECT transaction_id, transaction_date, description,
                       COALESCE(debit_amount,0) AS debit, COALESCE(credit_amount,0) AS credit
                FROM banking_transactions
                WHERE transaction_date >= '2019-01-01' AND transaction_date < '2020-01-01'
                  AND (
                     (COALESCE(debit_amount,0)::numeric BETWEEN %s AND %s) OR
                     (COALESCE(credit_amount,0)::numeric BETWEEN %s AND %s)
                  )
                ORDER BY transaction_date, transaction_id
                """,
                (AMT - TOL, AMT + TOL, AMT - TOL, AMT + TOL)
            )
            rows2 = cur.fetchall()
            if rows2:
                for r in rows2:
                    side = 'debit' if float(r[3] or 0) > 0 else 'credit'
                    amt = r[3] if side=='debit' else r[4]
                    print(f"  BANK   ID {r[0]} | {r[1]} | {side} ${amt:.2f} | {r[2]}")
            else:
                print("  No 2019 banking matches within ±$0.50 of $305.89.")
