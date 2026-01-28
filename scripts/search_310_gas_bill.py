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

AMT = Decimal('310.00')
START = '2018-12-01'
END = '2019-04-01'
TOL = Decimal('1.00')  # ±$1 tolerance

with psycopg2.connect(**DB) as conn:
    with conn.cursor() as cur:
        print(f"Searching for ~${AMT} (±${TOL}) in banking_transactions (Dec 2018 - Mar 2019)...")
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
            print(f"Found {len(rows)} match(es):")
            for r in rows:
                side = 'debit' if float(r[3] or 0) > 0 else 'credit'
                amt = r[3] if side=='debit' else r[4]
                print(f"  ID {r[0]} | {r[1]} | {side} ${amt:.2f} | {r[2]}")
        else:
            print("  No matches in Dec 2018 - Mar 2019. Expanding to full 2019...")
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
                print(f"Found {len(rows2)} match(es) in 2019:")
                for r in rows2:
                    side = 'debit' if float(r[3] or 0) > 0 else 'credit'
                    amt = r[3] if side=='debit' else r[4]
                    print(f"  ID {r[0]} | {r[1]} | {side} ${amt:.2f} | {r[2]}")
            else:
                print("  No matches found for $310 (±$1) in 2019.")

        print("\nSearching email_financial_events for ~$310...")
        cur.execute(
            """
            SELECT id, email_date, from_email, subject, amount, entity
            FROM email_financial_events
            WHERE email_date >= %s AND email_date < %s
              AND CAST(amount AS numeric) BETWEEN %s AND %s
            ORDER BY email_date
            """,
            (START, END, AMT - TOL, AMT + TOL)
        )
        email_rows = cur.fetchall()
        if email_rows:
            print(f"Found {len(email_rows)} email event(s):")
            for r in email_rows:
                print(f"  EMAIL ID {r[0]} | {r[1]} | ${r[4]} | {r[2]} | {r[3]} | entity={r[5]}")
        else:
            print("  No email events found in that range.")
