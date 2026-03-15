#!/usr/bin/env python3
"""
Audit unlinked banking withdrawals (cash/ATM) so they can be handled as transfers (Bank → Petty Cash), not receipts.

Read-only. Prints counts and a sample list for review.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

WITHDRAWAL_PATTERNS = [
    'withdrawal', 'atm', 'cash withdrawal'
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
    amt = amount_expr(bt_cols)

    like = " OR ".join(["LOWER(description) LIKE %s" for _ in WITHDRAWAL_PATTERNS])
    params = [f"%{p.lower()}%" for p in WITHDRAWAL_PATTERNS]

    cur.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM banking_transactions
        WHERE receipt_id IS NULL
          AND ({amt}) < 0
          AND ({like})
        """,
        params
    )
    count = cur.fetchone()['c']

    print('='*80)
    print('BANKING WITHDRAWALS (UNLINKED, CANDIDATE TRANSFERS)')
    print('='*80)
    print(f"Unlinked withdrawal candidates: {count}")

    # Show a sample
    cur.execute(
        f"""
        SELECT transaction_id, transaction_date, description, {amt} AS signed_amount
        FROM banking_transactions
        WHERE receipt_id IS NULL
          AND ({amt}) < 0
          AND ({like})
        ORDER BY transaction_date DESC
        LIMIT 25
        """,
        params
    )
    rows = cur.fetchall()

    if rows:
        print('\nRecent examples:')
        for r in rows:
            print(f"  {r['transaction_date']} | {r['transaction_id']} | {r['description']} | {r['signed_amount']}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
