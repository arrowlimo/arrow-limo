#!/usr/bin/env python3
"""
Reconcile Outlook-derived emails with banking_transactions for quick verification.

Inputs:
- l:/limo/reports/etransfer_emails.csv  (from extract_etransfers_from_outlook.py)
- l:/limo/reports/square_emails.csv     (from extract_square_from_outlook.py)

DB: Uses .env to connect to PostgreSQL and queries banking_transactions.

Outputs:
- l:/limo/reports/email_banking_reconciliation.csv (all matches)
- l:/limo/reports/email_banking_unmatched.csv (no banking match found)
"""
import os
import csv
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

ETRANSFER_CSV = r"l:/limo/reports/etransfer_emails.csv"
SQUARE_CSV = r"l:/limo/reports/square_emails.csv"
OUT_MATCHED = r"l:/limo/reports/email_banking_reconciliation.csv"
OUT_UNMATCHED = r"l:/limo/reports/email_banking_unmatched.csv"

AMOUNT_EPS = Decimal('0.01')
DATE_WINDOW_DAYS = 2


def dparse(s: str):
    try:
        return datetime.fromisoformat(str(s))
    except Exception:
        try:
            return datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def as_money(x) -> Decimal | None:
    if x in (None, ''):
        return None
    try:
        return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def get_conn():
    load_dotenv('l:/limo/.env'); load_dotenv()
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD',''),
        host=os.getenv('DB_HOST','localhost'),
        port=int(os.getenv('DB_PORT','5432')),
    )


def fetch_banking_candidates(cur, txn_date: datetime, amount: Decimal, kind: str):
    start = (txn_date - timedelta(days=DATE_WINDOW_DAYS)).date()
    end = (txn_date + timedelta(days=DATE_WINDOW_DAYS)).date()
    if kind == 'etransfer':
        sql = (
            "SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, account_number, vendor_extracted "
            "FROM banking_transactions "
            "WHERE transaction_date BETWEEN %s AND %s "
            "AND credit_amount IS NOT NULL "
            "AND ABS(credit_amount - %s) <= %s "
            "AND (description ILIKE '%%E-TRANSFER%%' OR description ILIKE '%%INTERAC%%' OR vendor_extracted ILIKE '%%INTERAC%%') "
            "ORDER BY transaction_date"
        )
        cur.execute(sql, (start, end, float(amount), float(AMOUNT_EPS)))
        return cur.fetchall()
    elif kind == 'square_payout':
        sql = (
            "SELECT transaction_id, transaction_date, description, credit_amount, debit_amount, account_number, vendor_extracted "
            "FROM banking_transactions "
            "WHERE transaction_date BETWEEN %s AND %s "
            "AND credit_amount IS NOT NULL "
            "AND ABS(credit_amount - %s) <= %s "
            "AND (description ILIKE '%%Square, Inc%%' OR vendor_extracted ILIKE '%%Square%%' OR description ILIKE '%%Electronic Funds Transfer%%Square%%') "
            "ORDER BY transaction_date"
        )
        cur.execute(sql, (start, end, float(amount), float(AMOUNT_EPS)))
        return cur.fetchall()
    else:
        return []


def read_csv_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        return list(r)


def main():
    et_rows = read_csv_rows(ETRANSFER_CSV)
    sq_rows = read_csv_rows(SQUARE_CSV)

    matched = []
    unmatched = []

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # E-Transfers
            for r in et_rows:
                amt = as_money(r.get('amount'))
                dt = dparse(r.get('email_date'))
                if not amt or not dt:
                    unmatched.append({'source':'etransfer', **r, 'reason':'missing_amount_or_date'})
                    continue
                candidates = fetch_banking_candidates(cur, dt, amt, 'etransfer')
                if candidates:
                    for c in candidates:
                        matched.append({
                            'source':'etransfer',
                            'email_uid': r.get('uid'),
                            'email_date': r.get('email_date'),
                            'email_subject': r.get('subject'),
                            'amount': str(amt),
                            'bank_txn_id': c['transaction_id'],
                            'bank_date': c['transaction_date'],
                            'bank_amount': c['credit_amount'],
                            'bank_desc': c['description'],
                            'bank_vendor': c.get('vendor_extracted'),
                        })
                else:
                    unmatched.append({'source':'etransfer', **r, 'reason':'no_banking_match'})

            # Square payouts (from square_emails)
            for r in sq_rows:
                typ = (r.get('type') or '').lower()
                if typ != 'payout':
                    continue
                amt = as_money(r.get('amount'))
                dt = dparse(r.get('email_date'))
                if not amt or not dt:
                    unmatched.append({'source':'square_payout', **r, 'reason':'missing_amount_or_date'})
                    continue
                candidates = fetch_banking_candidates(cur, dt, amt, 'square_payout')
                if candidates:
                    for c in candidates:
                        matched.append({
                            'source':'square_payout',
                            'email_uid': r.get('uid'),
                            'email_date': r.get('email_date'),
                            'email_subject': r.get('subject'),
                            'amount': str(amt),
                            'bank_txn_id': c['transaction_id'],
                            'bank_date': c['transaction_date'],
                            'bank_amount': c['credit_amount'],
                            'bank_desc': c['description'],
                            'bank_vendor': c.get('vendor_extracted'),
                        })
                else:
                    unmatched.append({'source':'square_payout', **r, 'reason':'no_banking_match'})

    os.makedirs('l:/limo/reports', exist_ok=True)
    with open(OUT_MATCHED, 'w', newline='', encoding='utf-8') as f:
        if matched:
            w = csv.DictWriter(f, fieldnames=list(matched[0].keys()))
            w.writeheader(); w.writerows(matched)
        else:
            f.write('')
    with open(OUT_UNMATCHED, 'w', newline='', encoding='utf-8') as f:
        if unmatched:
            # normalize headers
            keys = set()
            for s in unmatched:
                keys.update(s.keys())
            w = csv.DictWriter(f, fieldnames=sorted(keys))
            w.writeheader(); w.writerows(unmatched)
        else:
            f.write('')

    print(f"Email reconciliation complete: matched={len(matched)} unmatched={len(unmatched)}")
    print(' ', OUT_MATCHED)
    print(' ', OUT_UNMATCHED)


if __name__ == '__main__':
    main()
