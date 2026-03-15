#!/usr/bin/env python3
"""
Audit deposit banking transactions and try to find matches in payments by date and amount.

Read-only. Outputs overall counts and a few unmatched examples.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

DEPOSIT_PATTERNS = [
    'deposit', 'cheque', 'check', 'ck ', 'cash deposit', 'branch deposit'
]


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def get_columns(cur, table):
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    return [r['column_name'] for r in cur.fetchall()]


def amount_expr(cols):
    if 'debit_amount' in cols and 'credit_amount' in cols:
        return '(COALESCE(credit_amount,0) - COALESCE(debit_amount,0))'
    elif 'amount' in cols:
        return 'amount'
    return '0'


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    bt_cols = get_columns(cur, 'banking_transactions')
    pm_cols = get_columns(cur, 'payments')

    amt = amount_expr(bt_cols)

    # Choose payments amount/date columns defensively
    p_amount_col = 'amount' if 'amount' in pm_cols else ('payment_amount' if 'payment_amount' in pm_cols else None)
    p_date_col = 'payment_date' if 'payment_date' in pm_cols else ('created_at' if 'created_at' in pm_cols else None)

    if p_amount_col is None or p_date_col is None:
        print('Payments table is missing amount/date columns for this audit (skipping).')
        return

    like = " OR ".join(["LOWER(b.description) LIKE %s" for _ in DEPOSIT_PATTERNS])
    params = [f"%{p.lower()}%" for p in DEPOSIT_PATTERNS]

    # Count deposit candidates
    cur.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM banking_transactions b
        WHERE ({amt}) > 0
          AND ({like})
        """,
        params
    )
    deposit_total = cur.fetchone()['c']

    # Matches by exact date and amount
    cur.execute(
        f"""
        WITH deposits AS (
            SELECT b.transaction_id, b.transaction_date, {amt} AS amount
            FROM banking_transactions b
            WHERE ({amt}) > 0
              AND ({like})
        )
        SELECT COUNT(*) AS matched
        FROM deposits d
        JOIN payments p
          ON p.{p_date_col}::date = d.transaction_date::date
         AND COALESCE(p.{p_amount_col}, 0) = COALESCE(d.amount, 0)
        """,
        params
    )
    matched = cur.fetchone()['matched']

    print('='*80)
    print('BANKING DEPOSITS → PAYMENTS MATCH AUDIT')
    print('='*80)
    print(f"Deposit candidates: {deposit_total}")
    print(f"Matched by date+amount: {matched}")
    print(f"Unmatched: {deposit_total - matched}")

    # Show some unmatched examples
    cur.execute(
        f"""
        WITH deposits AS (
            SELECT b.transaction_id, b.transaction_date, b.description, {amt} AS amount
            FROM banking_transactions b
            WHERE ({amt}) > 0
              AND ({like})
        ), matches AS (
            SELECT d.transaction_id
            FROM deposits d
            JOIN payments p
              ON p.{p_date_col}::date = d.transaction_date::date
             AND COALESCE(p.{p_amount_col}, 0) = COALESCE(d.amount, 0)
        )
        SELECT d.transaction_id, d.transaction_date, d.description, d.amount
        FROM deposits d
        LEFT JOIN matches m ON m.transaction_id = d.transaction_id
        WHERE m.transaction_id IS NULL
        ORDER BY d.transaction_date DESC
        LIMIT 15
        """,
        params
    )
    rows = cur.fetchall()
    if rows:
        print('\nSample unmatched deposits:')
        for r in rows:
            print(f"  {r['transaction_date']} | {r['transaction_id']} | {r['description']} | {r['amount']}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
