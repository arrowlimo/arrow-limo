#!/usr/bin/env python3
"""
Comprehensive Square Payment to LMS Matcher - Postgres Variant (payment_key based)

This variant identifies Square payments by `payment_method='credit_card'` and `payment_key IS NOT NULL`
and links them to charters using LMS unified data, deposits, reserves, and CIBC banking validation.

Usage:
  python -X utf8 scripts/square_to_lms_matcher_postgres_paymentkey.py --report-only
  python -X utf8 scripts/square_to_lms_matcher_postgres_paymentkey.py --apply --min-confidence 3
"""
import os
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from datetime import datetime, timedelta
import argparse

load_dotenv('l:/limo/.env'); load_dotenv()

PG_HOST = os.getenv('DB_HOST','localhost')
PG_PORT = int(os.getenv('DB_PORT','5432'))
PG_NAME = os.getenv('DB_NAME','almsdata')
PG_USER = os.getenv('DB_USER','postgres')
PG_PASSWORD = os.getenv('DB_PASSWORD','')

def get_pg_conn():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_NAME, user=PG_USER, password=PG_PASSWORD)

# Import core matching helpers from the original module by reading its code is heavy.
# Instead, we duplicate the minimal needed subset by reusing functions through local definitions.
# To keep the file short, we inline small helpers and reuse SQL logic directly.

def get_unmatched_square_payments():
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT payment_id, payment_date, amount, payment_key AS square_payment_id,
                       notes, square_customer_name, square_customer_email, square_last4
                  FROM payments
                 WHERE payment_method = 'credit_card'
                   AND payment_key IS NOT NULL
                   AND charter_id IS NULL
                 ORDER BY payment_date DESC
                """
            )
            return cur.fetchall()

def get_lms_unified_data():
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT payment_id, reserve_no, payment_amount, payment_date_text,
                       deposit_key, number as deposit_number, deposit_total, deposit_date,
                       payment_method, payment_key
                  FROM lms_unified_map
                 ORDER BY payment_id
                """
            )
            return cur.fetchall()

def get_lms_deposits():
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT dep_key as deposit_key, number as deposit_number,
                       total as deposit_total, dep_date as deposit_date,
                       type as deposit_type, transact
                  FROM lms_deposits
                 ORDER BY dep_date DESC
                """
            )
            return cur.fetchall()

def get_lms_reserves():
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT reserve_no, pu_date_text as pu_date, rate, balance, deposit,
                       status, pymt_type
                  FROM lms_reserves
                 ORDER BY reserve_no
                """
            )
            return cur.fetchall()

def get_lms_charges():
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT charge_id, reserve_no, account_no, amount, description,
                       rate, sequence, last_updated
                  FROM lms_charges
                 WHERE amount > 0
                 ORDER BY reserve_no, charge_id
                """
            )
            return cur.fetchall()

def get_cibc_banking_transactions():
    with get_pg_conn() as pg_conn:
        with pg_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT transaction_id, transaction_date,
                       COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0) as amount,
                       description, account_number
                  FROM banking_transactions
                 WHERE description ILIKE '%square%'
                    OR description ILIKE '%electronic funds transfer%'
                 ORDER BY transaction_date DESC
                """
            )
            return cur.fetchall()

# Import the original matcher functions by executing within this namespace to avoid code drift
# We will read the file and exec only the functions we need: match_square_to_lms_comprehensive, apply_matches, save_matches_report
from types import SimpleNamespace

def _load_original_impl():
    src_path = os.path.join('l:/limo/scripts', 'square_to_lms_matcher_postgres.py')
    ns: dict = {}
    with open(src_path, 'r', encoding='utf-8') as f:
        code = f.read()
    # Execute in isolated namespace, then extract required names
    exec(compile(code, src_path, 'exec'), ns, ns)
    return SimpleNamespace(
        match_square_to_lms_comprehensive=ns['match_square_to_lms_comprehensive'],
        apply_matches=ns['apply_matches'],
        save_matches_report=ns['save_matches_report'],
        build_customer_resolution_indexes=ns['build_customer_resolution_indexes'],
        build_last4_index=ns['build_last4_index'],
        find_best_charter_for_client=ns['find_best_charter_for_client'],
    )

impl = _load_original_impl()


def main():
    ap = argparse.ArgumentParser(description='Match Square payments to LMS charters using Postgres (payment_key variant)')
    ap.add_argument('--min-confidence', type=int, default=4, help='Minimum confidence to auto-apply matches')
    ap.add_argument('--apply', action='store_true', help='Apply high-confidence matches to database')
    ap.add_argument('--report-only', action='store_true', help='Generate report only, do not apply matches')
    args = ap.parse_args()

    print('Loading data for payment_key-based Square matching...')
    square_payments = get_unmatched_square_payments()
    unified_data = get_lms_unified_data()
    lms_deposits = get_lms_deposits()
    lms_reserves = get_lms_reserves()
    lms_charges = get_lms_charges()
    cibc_transactions = get_cibc_banking_transactions()

    print(f"Data loaded: square={len(square_payments)}, unified={len(unified_data)}, deposits={len(lms_deposits)}, reserves={len(lms_reserves)}, charges={len(lms_charges)}, cibc={len(cibc_transactions)}")

    matches = impl.match_square_to_lms_comprehensive(square_payments, unified_data, lms_deposits, lms_reserves, lms_charges, cibc_transactions, retainer_map=None)

    report_file = impl.save_matches_report(matches)

    applied_count = 0
    if args.apply and not args.report_only:
        # Lower threshold to 3 (same as original suggestion)
        applied_count = impl.apply_matches(matches, min_confidence=max(3, args.min_confidence))

    print(f"\nCompleted. Report: {report_file}")
    if applied_count:
        print(f"Applied {applied_count} matches.")

if __name__ == '__main__':
    main()
