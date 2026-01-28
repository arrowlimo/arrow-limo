#!/usr/bin/env python3
"""
Reconcile email_financial_events to banking_transactions by amount/date window.
Updates email_financial_events.banking_transaction_id and matched_account_number.
"""
import os
from datetime import timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Pull events needing reconciliation
    cur.execute(
        """
        SELECT id, email_date::date AS edate, amount::numeric AS amount, entity, event_type
        FROM email_financial_events
        WHERE banking_transaction_id IS NULL
          AND amount IS NOT NULL
          AND email_date IS NOT NULL
        ORDER BY email_date
        """
    )
    events = cur.fetchall()
    matched = 0

    for ev in events:
        amt = float(ev['amount']) if ev['amount'] is not None else None
        if amt is None or amt <= 0:
            continue
        edate = ev['edate']

        # Choose direction by event_type: payments are debits, loan deposits/credits would be credits
        prefer_debit = ev['event_type'] in ('loan_payment','insurance_payment','nsf_fee')
        prefer_credit = ev['event_type'] in ('loan_opened','downpayment','extra_payment')

        cur.execute(
            """
            SELECT transaction_id, transaction_date, description, account_number,
                   debit_amount::numeric AS debit_amount, credit_amount::numeric AS credit_amount,
                   CASE WHEN debit_amount IS NOT NULL THEN ABS(debit_amount - %s)
                        WHEN credit_amount IS NOT NULL THEN ABS(credit_amount - %s)
                        ELSE 999999 END AS amt_diff
            FROM banking_transactions
            WHERE transaction_date BETWEEN %s::date - INTERVAL '3 day' AND %s::date + INTERVAL '5 day'
              AND (debit_amount IS NOT NULL OR credit_amount IS NOT NULL)
              AND (ABS(COALESCE(debit_amount,0) - %s) < 0.02 OR ABS(COALESCE(credit_amount,0) - %s) < 0.02)
            ORDER BY amt_diff ASC, transaction_date ASC
            LIMIT 5
            """,
            (amt, amt, edate, edate, amt, amt)
        )
        candidates = cur.fetchall()
        choice = None
        for c in candidates:
            # simple preference: if payment then pick debit, else credit; otherwise pick first
            if prefer_debit and c['debit_amount'] is not None:
                choice = c; break
            if prefer_credit and c['credit_amount'] is not None:
                choice = c; break
        if choice is None and candidates:
            choice = candidates[0]

        if choice:
            cur.execute(
                """
                UPDATE email_financial_events
                   SET banking_transaction_id = %s,
                       matched_account_number = %s
                 WHERE id = %s
                """,
                (choice['transaction_id'], choice['account_number'], ev['id'])
            )
            matched += 1

    conn.commit()
    cur.close(); conn.close()
    print(f"Reconciled {matched} email events to banking transactions")


if __name__ == '__main__':
    main()
