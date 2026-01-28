#!/usr/bin/env python3
"""
Extract CIBC INTERAC e-Transfer accepted events (e.g., to Willie Heffner) from email_financial_events
and update missing amounts by parsing the subject/body text, then reconcile to banking_transactions.
"""
import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

AMOUNT_RE = re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2}))")


def main():
    load_dotenv('l:/limo/.env'); load_dotenv()
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Pull CIBC e-Transfer accepted emails that likely target Willie Heffner
    cur.execute(
        """
        SELECT id, subject, notes, amount, email_date
        FROM email_financial_events
        WHERE (subject ILIKE '%INTERAC e-Transfer%' OR subject ILIKE '%INTERAC E-TRANSFER%')
          AND (subject ILIKE '%accepted%' OR subject ILIKE '%accepted%')
          AND (subject ILIKE '%Willie Heffner%' OR notes ILIKE '%Willie Heffner%')
        ORDER BY email_date
        """
    )
    rows = cur.fetchall()
    updated = 0
    for r in rows:
        if r['amount'] is None:
            m = AMOUNT_RE.search(r['subject'] or '') or AMOUNT_RE.search(r.get('notes') or '')
            if m:
                amt = float(m.group(1).replace(',', ''))
                cur.execute("UPDATE email_financial_events SET amount = %s WHERE id = %s", (amt, r['id']))
                updated += 1
    conn.commit()
    print(f"Updated amounts for {updated} e-Transfer emails")

    # Optional: call reconciliation pass to banking
    # We inline a simple reconciliation on these specific events
    matched = 0
    for r in rows:
        cur.execute("SELECT amount, email_date::date FROM email_financial_events WHERE id = %s", (r['id'],))
        ev = cur.fetchone()
        if not ev or ev['amount'] is None:
            continue
        amt = float(ev['amount'])
        edate = ev['email_date']
        cur.execute(
            """
            SELECT transaction_id, account_number
              FROM banking_transactions
             WHERE transaction_date BETWEEN %s::date - INTERVAL '3 day' AND %s::date + INTERVAL '5 day'
               AND debit_amount IS NOT NULL AND ABS(debit_amount - %s) < 0.02
             ORDER BY transaction_date ASC
             LIMIT 1
            """,
            (edate, edate, amt)
        )
        cand = cur.fetchone()
        if cand:
            cur.execute(
                "UPDATE email_financial_events SET banking_transaction_id=%s, matched_account_number=%s WHERE id=%s",
                (cand['transaction_id'], cand['account_number'], r['id'])
            )
            matched += 1
    conn.commit()
    cur.close(); conn.close()
    print(f"Reconciled {matched} Willie Heffner e-Transfers to banking")


if __name__ == '__main__':
    main()
