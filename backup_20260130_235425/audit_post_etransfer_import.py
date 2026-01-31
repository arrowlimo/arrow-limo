#!/usr/bin/env python3
"""Comprehensive audit after e-transfer payment import.

Outputs (no writes unless --backup provided):
  1. Overpayment summary (charters with balance < 0)
  2. Outstanding balances (balance > 0) top 25 + totals
  3. Confirmation deposit vs payments consistency (mismatch >5% or >$2)
  4. E-transfer payment method / amount distribution (payment_key LIKE 'ETR:%')
  5. Optional backups of payments & charters tables (CREATE TABLE AS SELECT)

Usage:
  python audit_post_etransfer_import.py            # read-only report
  python audit_post_etransfer_import.py --backup   # also create backups

Backups:
  payments_backup_post_etransfer_YYYYMMDD_HHMMSS
  charters_backup_post_etransfer_YYYYMMDD_HHMMSS
"""

import os
import psycopg2
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def fmt_money(val):
    if val is None:
        return "$0.00"
    return f"${val:,.2f}"


def overpayment_summary(cur):
    cur.execute("""
        SELECT COUNT(*), SUM(ABS(balance))
        FROM charters
        WHERE balance < 0
    """)
    count, total = cur.fetchone()
    print("\n[1] Overpayments")
    print(f"  Charters overpaid: {count}")
    print(f"  Total negative balance absorbed: {fmt_money(total)}")
    cur.execute("""
        SELECT reserve_number, balance, total_amount_due, paid_amount
        FROM charters
        WHERE balance < 0
        ORDER BY balance ASC
        LIMIT 15
    """)
    rows = cur.fetchall()
    if rows:
        print("  Sample (most negative):")
        for r in rows:
            rn, bal, due, paid = r
            print(f"    {rn} balance={fmt_money(bal)} due={fmt_money(due)} paid={fmt_money(paid)}")


def outstanding_summary(cur):
    cur.execute("""
        SELECT COUNT(*), SUM(balance)
        FROM charters
        WHERE balance > 0
    """)
    count, total = cur.fetchone()
    print("\n[2] Outstanding Balances")
    print(f"  Charters with amount owing: {count}")
    print(f"  Total outstanding: {fmt_money(total)}")
    cur.execute("""
        SELECT reserve_number, balance, total_amount_due, paid_amount
        FROM charters
        WHERE balance > 0
        ORDER BY balance DESC
        LIMIT 25
    """)
    rows = cur.fetchall()
    print("  Top 25 owing:")
    for r in rows:
        rn, bal, due, paid = r
        print(f"    {rn} balance={fmt_money(bal)} due={fmt_money(due)} paid={fmt_money(paid)}")


def confirmation_consistency(cur):
    print("\n[3] Confirmation Deposit Consistency")
    # Events with deposit amount
    cur.execute("""
        WITH conf AS (
            SELECT id, matched_account_number AS reserve_number, amount AS deposit, email_date::date AS email_date
            FROM email_financial_events
            WHERE source='outlook_charter_confirmation'
              AND matched_account_number IS NOT NULL
              AND amount IS NOT NULL
        ), pay AS (
            SELECT payment_id, reserve_number, amount, payment_date
            FROM payments
        ), joined AS (
            SELECT conf.id AS event_id, conf.reserve_number, conf.deposit, pay.amount AS payment_amount,
                   conf.email_date, pay.payment_date,
                   ABS(conf.deposit - pay.amount) AS diff,
                   CASE WHEN pay.amount IS NOT NULL THEN ABS(conf.deposit - pay.amount)/NULLIF(pay.amount,0) END AS pct_diff
            FROM conf
            LEFT JOIN pay ON pay.reserve_number = conf.reserve_number
              AND (pay.payment_date BETWEEN conf.email_date - INTERVAL '7 days' AND conf.email_date + INTERVAL '30 days')
        )
        SELECT COUNT(*) FILTER (WHERE payment_amount IS NOT NULL) AS matched_events,
               COUNT(*) FILTER (WHERE payment_amount IS NULL) AS unmatched_events,
               COUNT(*) FILTER (WHERE payment_amount IS NOT NULL AND (pct_diff > 0.05 AND diff > 2)) AS mismatched_events
        FROM joined
    """)
    matched, unmatched, mismatched = cur.fetchone()
    print(f"  Events with related payment: {matched}")
    print(f"  Events with no nearby payment: {unmatched}")
    print(f"  Payment mismatch events (>5% and >$2): {mismatched}")
    # Show sample mismatches
    cur.execute("""
        WITH conf AS (
            SELECT id, matched_account_number AS reserve_number, amount AS deposit, email_date::date AS email_date
            FROM email_financial_events
            WHERE source='outlook_charter_confirmation'
              AND matched_account_number IS NOT NULL
              AND amount IS NOT NULL
        ), pay AS (
            SELECT payment_id, reserve_number, amount, payment_date
            FROM payments
        ), joined AS (
            SELECT conf.id AS event_id, conf.reserve_number, conf.deposit, pay.amount AS payment_amount,
                   conf.email_date, pay.payment_date,
                   ABS(conf.deposit - pay.amount) AS diff,
                   CASE WHEN pay.amount IS NOT NULL THEN ABS(conf.deposit - pay.amount)/NULLIF(pay.amount,0) END AS pct_diff
            FROM conf
            LEFT JOIN pay ON pay.reserve_number = conf.reserve_number
              AND (pay.payment_date BETWEEN conf.email_date - INTERVAL '7 days' AND conf.email_date + INTERVAL '30 days')
        )
        SELECT reserve_number, deposit, payment_amount, diff, pct_diff
        FROM joined
        WHERE payment_amount IS NOT NULL AND (pct_diff > 0.05 AND diff > 2)
        ORDER BY diff DESC
        LIMIT 15
    """)
    rows = cur.fetchall()
    if rows:
        print("  Sample mismatches:")
        for rn, dep, pay_amt, diff, pct in rows:
            pct_disp = f"{pct*100:.1f}%" if pct is not None else "N/A"
            print(f"    {rn} deposit={fmt_money(dep)} payment={fmt_money(pay_amt)} diff={fmt_money(diff)} pct={pct_disp}")


def etransfer_distribution(cur):
    print("\n[4] E-Transfer Payment Distribution (inserted ETR:* keys)")
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM payments
        WHERE payment_key LIKE 'ETR:%'
    """)
    count, total = cur.fetchone()
    print(f"  Imported e-transfer payments: {count} total={fmt_money(total)}")
    cur.execute("""
        SELECT payment_method, COUNT(*), SUM(amount)
        FROM payments
        WHERE payment_key LIKE 'ETR:%'
        GROUP BY payment_method
        ORDER BY SUM(amount) DESC
    """)
    rows = cur.fetchall()
    for m, c, s in rows:
        print(f"    {m or 'NULL'}: {c} {fmt_money(s)}")


def create_backups(cur):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    pay_backup = f"payments_backup_post_etransfer_{ts}"
    char_backup = f"charters_backup_post_etransfer_{ts}"
    print("\n[5] Creating backups...")
    cur.execute(f"CREATE TABLE {pay_backup} AS SELECT * FROM payments")
    cur.execute(f"CREATE TABLE {char_backup} AS SELECT * FROM charters")
    print(f"  Created {pay_backup}")
    print(f"  Created {char_backup}")
    return pay_backup, char_backup


def main():
    parser = argparse.ArgumentParser(description="Post-import audit for e-transfer payments")
    parser.add_argument('--backup', action='store_true', help='Create backup tables')
    args = parser.parse_args()
    conn = get_conn()
    cur = conn.cursor()

    overpayment_summary(cur)
    outstanding_summary(cur)
    confirmation_consistency(cur)
    etransfer_distribution(cur)
    if args.backup:
        create_backups(cur)
    conn.commit()
    cur.close(); conn.close()


if __name__ == '__main__':
    main()
