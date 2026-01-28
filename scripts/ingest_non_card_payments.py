#!/usr/bin/env python3
"""
Ingest non-card customer payments (Interac e-Transfers, cheques, cash) from banking_transactions
into the payments table as independent payment records (not Square). Produces a candidates CSV
for linking these payments to charters later.

- Interac e-Transfers: banking_transactions.description contains 'E-TRANSFER' or 'INTERAC'
- Cheques: banking_transactions.description contains 'CHEQUE' or 'CHECK' or 'CHQ'
- Cash: small deposits likely recorded as cash; banking_transactions.description contains 'CASH'

Rules:
- Only consider credits (inflows)
- Only consider dates within LOOKBACK_DAYS (env PAY_INGEST_LOOKBACK_DAYS, default 180)
- Skip amounts that match Square payouts in the same date window to avoid double counting
- Upsert into payments with payment_method in {'etransfer','cheque','cash'} and payment_key pattern BTX:<transaction_id>
- Notes include the banking description and account tail

Outputs:
- reports/non_card_payment_candidates.csv - raw extracted rows from banking for review

Safe to run multiple times (idempotent by payment_key 'BTX:<transaction_id>').
"""
import os
import csv
from datetime import date, timedelta
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')
LOOKBACK_DAYS = int(os.getenv('PAY_INGEST_LOOKBACK_DAYS','180'))
CSV_OUT = 'l:/limo/reports/non_card_payment_candidates.csv'

# IMPORTANT: escape % as %% so psycopg2 doesn't treat them as formatting placeholders
INTERAC_PAT = "(description ILIKE '%%E-TRANSFER%%' OR description ILIKE '%%INTERAC%%')"
CHEQUE_PAT = "(description ILIKE '%%CHEQUE%%' OR description ILIKE '%%CHECK%%' OR description ILIKE '%%CHQ%%')"
CASH_PAT = "(description ILIKE '%%CASH%%')"

NON_CARD_METHODS = {
    'etransfer': INTERAC_PAT,
    'cheque': CHEQUE_PAT,
    'cash': CASH_PAT,
}


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def fetch_square_payout_amounts(cur, start_date, end_date):
    cur.execute(
        """
        SELECT arrival_date::date, ROUND(CAST(amount AS NUMERIC), 2) AS amt
          FROM square_payouts
         WHERE arrival_date BETWEEN %s AND %s
        """,
        (start_date, end_date)
    )
    payouts = {}
    for d, amt in cur.fetchall():
        payouts.setdefault(d, set()).add(float(amt))
    return payouts


def collect_candidates():
    today = date.today()
    start_date = today - timedelta(days=LOOKBACK_DAYS)
    out_rows = []
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Square payout amounts by date to filter out
            sq_by_date = fetch_square_payout_amounts(cur, start_date, today)

            for method, where_pat in NON_CARD_METHODS.items():
                # Use literal dates to avoid placeholder counting issues with %% in LIKE patterns
                sql = f"""
                    SELECT transaction_id, transaction_date::date, description, credit_amount, account_number
                      FROM banking_transactions
                     WHERE transaction_date BETWEEN DATE '{start_date}' AND DATE '{today}'
                       AND credit_amount IS NOT NULL AND credit_amount > 0
                       AND {where_pat}
                     ORDER BY transaction_date DESC
                """
                cur.execute(sql)
                for tid, tdate, desc, credit, acct in cur.fetchall():
                    # Skip if this credit equals a Square payout amount on same date
                    same_day = sq_by_date.get(tdate, set())
                    if round(float(credit), 2) in same_day:
                        continue
                    out_rows.append({
                        'transaction_id': tid,
                        'payment_date': tdate.isoformat(),
                        'amount': round(float(credit), 2),
                        'method': method,
                        'description': desc,
                        'account_tail': str(acct)[-4:] if acct else None,
                    })
    return out_rows


def upsert_payments(rows):
    inserted = 0
    updated = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for r in rows:
                pkey = f"BTX:{r['transaction_id']}"
                cur.execute("SELECT payment_id FROM payments WHERE payment_key = %s", (pkey,))
                ex = cur.fetchone()
                if ex:
                    cur.execute(
                        """
                        UPDATE payments
                           SET amount = %s,
                               payment_date = %s,
                               payment_method = %s,
                               notes = %s,
                               last_updated = NOW()
                         WHERE payment_id = %s
                        """,
                        (
                                r['amount'], r['payment_date'],
                                # Map to allowed set per constraint: cash, check, credit_card, debit_card, bank_transfer, unknown
                                ('bank_transfer' if r['method']=='etransfer' else ('check' if r['method']=='cheque' else ('cash' if r['method']=='cash' else 'unknown'))),
                            f"[Bank {r['account_tail']}] {r['description']}", ex[0]
                        )
                    )
                    updated += 1
                else:
                    cur.execute(
                        """
                        INSERT INTO payments (amount, payment_date, charter_id, payment_method, payment_key, notes, last_updated, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                        """,
                        (
                            r['amount'], r['payment_date'], None,
                            ('bank_transfer' if r['method']=='etransfer' else ('check' if r['method']=='cheque' else ('cash' if r['method']=='cash' else 'unknown'))),
                            pkey,
                            f"[Bank {r['account_tail']}] {r['description']}"
                        )
                    )
                    inserted += 1
        conn.commit()
    return inserted, updated


def write_csv(rows):
    os.makedirs(os.path.dirname(CSV_OUT), exist_ok=True)
    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['transaction_id','payment_date','amount','method','account_tail','description'])
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows = collect_candidates()
    write_csv(rows)
    ins, upd = upsert_payments(rows)
    print(f"Non-card payments candidates: {len(rows)} | inserted: {ins} | updated: {upd}")
    print(f"CSV: {CSV_OUT}")

if __name__ == '__main__':
    main()
