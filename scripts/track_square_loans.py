#!/usr/bin/env python3
"""
Track Square loan payments using Outlook-derived emails and reconcile to banking debits.

Data sources:
  - reports/square_emails.csv (type=loan_payment rows with amount and date)
  - banking_transactions (debits)

DB artifacts:
  - Create table square_loan_payments if not exists

Outputs:
  - reports/square_loan_matches.csv
  - reports/square_loan_unmatched.csv
"""
import os
import csv
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

CSV_IN = r"l:/limo/reports/square_emails.csv"
CSV_MATCH = r"l:/limo/reports/square_loan_matches.csv"
CSV_UNMATCH = r"l:/limo/reports/square_loan_unmatched.csv"

DATE_WINDOW_DAYS = int(os.getenv('SQUARE_LOAN_DATE_WINDOW_DAYS','5'))
AMOUNT_TOL = float(os.getenv('SQUARE_LOAN_AMOUNT_TOLERANCE','1.00'))


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS square_loan_payments (
            id SERIAL PRIMARY KEY,
            email_uid TEXT,
            email_date TIMESTAMPTZ,
            amount NUMERIC(12,2),
            currency TEXT,
            message_id TEXT,
            banking_transaction_id TEXT,
            banking_date DATE,
            banking_amount NUMERIC(12,2),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(message_id)
        )
        """
    )


def load_email_rows():
    if not os.path.exists(CSV_IN):
        return []
    out = []
    with open(CSV_IN, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get('type') or '').lower() != 'loan_payment':
                continue
            try:
                amt = float(row.get('amount') or 0)
                dt = row.get('email_date')
                out.append({
                    'email_uid': row.get('uid') or '',
                    'message_id': row.get('message_id') or '',
                    'email_date': datetime.fromisoformat(dt) if dt else None,
                    'amount': round(amt, 2),
                    'currency': row.get('currency') or 'CAD',
                })
            except Exception:
                continue
    return out


def reconcile_and_upsert(rows):
    matched = []
    unmatched = []
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            ensure_table(cur)
            for r in rows:
                # Find matching banking debit
                cur.execute(
                    """
                    SELECT transaction_id, transaction_date, debit_amount, description
                      FROM banking_transactions
                     WHERE transaction_date BETWEEN %s::date - %s AND %s::date + %s
                       AND debit_amount IS NOT NULL AND debit_amount > 0
                     ORDER BY ABS(debit_amount - %s) ASC, transaction_date ASC
                     LIMIT 5
                    """,
                    (r['email_date'].date() if r['email_date'] else None, DATE_WINDOW_DAYS,
                     r['email_date'].date() if r['email_date'] else None, DATE_WINDOW_DAYS,
                     r['amount'])
                )
                cand = cur.fetchall()
                best = None
                for c in cand:
                    if abs(float(c['debit_amount']) - float(r['amount'])) <= AMOUNT_TOL:
                        best = c
                        break
                # Upsert record
                cur.execute("SELECT id FROM square_loan_payments WHERE message_id=%s", (r['message_id'],))
                exists = cur.fetchone()
                if best:
                    if exists:
                        cur.execute(
                            """
                            UPDATE square_loan_payments
                               SET email_uid=%s, email_date=%s, amount=%s, currency=%s,
                                   banking_transaction_id=%s, banking_date=%s, banking_amount=%s
                             WHERE id=%s
                            """,
                            (r['email_uid'], r['email_date'], r['amount'], r['currency'],
                             best['transaction_id'], best['transaction_date'], best['debit_amount'], exists['id'])
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO square_loan_payments (email_uid, email_date, amount, currency, message_id,
                                                              banking_transaction_id, banking_date, banking_amount)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                            RETURNING id
                            """,
                            (r['email_uid'], r['email_date'], r['amount'], r['currency'], r['message_id'],
                             best['transaction_id'], best['transaction_date'], best['debit_amount'])
                        )
                    matched.append({
                        **r,
                        'bank_txn_id': best['transaction_id'],
                        'bank_date': best['transaction_date'],
                        'bank_amount': float(best['debit_amount']),
                    })
                else:
                    if not exists:
                        cur.execute(
                            """
                            INSERT INTO square_loan_payments (email_uid, email_date, amount, currency, message_id)
                            VALUES (%s,%s,%s,%s,%s)
                            RETURNING id
                            """,
                            (r['email_uid'], r['email_date'], r['amount'], r['currency'], r['message_id'])
                        )
                    unmatched.append(r)
            conn.commit()
    return matched, unmatched


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        if not rows:
            f.write(''); return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def main():
    rows = load_email_rows()
    matched, unmatched = reconcile_and_upsert(rows)
    write_csv(CSV_MATCH, matched)
    write_csv(CSV_UNMATCH, unmatched)
    print(f"Square loan tracking complete: matched={len(matched)}, unmatched={len(unmatched)}")
    print(' ', CSV_MATCH)
    print(' ', CSV_UNMATCH)


if __name__ == '__main__':
    main()
