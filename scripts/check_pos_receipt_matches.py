#!/usr/bin/env python3
"""
Check if unlinked POS purchases have matching receipts by date+amount (just not linked yet).
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def get_columns(cur, table):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    return [r['column_name'] for r in cur.fetchall()]


def amount_expr(cols):
    if 'debit_amount' in cols and 'credit_amount' in cols:
        return '(COALESCE(credit_amount,0) - COALESCE(debit_amount,0))'
    elif 'amount' in cols:
        return 'amount'
    return '0'


POS_PATTERNS = ['pos purchase', 'point of sale', 'debit purchase', 'visa purchase']


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    bt_cols = get_columns(cur, 'banking_transactions')
    rc_cols = get_columns(cur, 'receipts')
    
    bt_amt = amount_expr(bt_cols)
    
    # Find receipt amount column
    rc_amount_col = 'gross_amount' if 'gross_amount' in rc_cols else ('amount' if 'amount' in rc_cols else None)
    rc_date_col = 'receipt_date' if 'receipt_date' in rc_cols else ('created_at' if 'created_at' in rc_cols else None)
    
    if not rc_amount_col or not rc_date_col:
        print("Receipts table missing required columns; cannot match.")
        return

    like = " OR ".join(["LOWER(b.description) LIKE %s" for _ in POS_PATTERNS])
    params = [f"%{p.lower()}%" for p in POS_PATTERNS]

    # Count unlinked POS
    cur.execute(
        f"""
        SELECT COUNT(*) AS c
        FROM banking_transactions b
        WHERE b.receipt_id IS NULL
          AND ({bt_amt}) < 0
          AND ({like})
        """,
        params
    )
    unlinked_pos = cur.fetchone()['c']

    # Count how many have potential receipt matches (date + amount within $0.01)
    cur.execute(
        f"""
        WITH pos AS (
            SELECT b.transaction_id, b.transaction_date, ABS({bt_amt}) AS amount
            FROM banking_transactions b
            WHERE b.receipt_id IS NULL
              AND ({bt_amt}) < 0
              AND ({like})
        )
        SELECT COUNT(DISTINCT pos.transaction_id) AS matched
        FROM pos
        JOIN receipts r
          ON r.{rc_date_col}::date = pos.transaction_date::date
         AND ABS(COALESCE(r.{rc_amount_col}, 0) - pos.amount) <= 0.01
        """,
        params
    )
    matchable = cur.fetchone()['matched']

    print('='*80)
    print('POS PURCHASES vs RECEIPTS MATCH CHECK')
    print('='*80)
    print(f"Unlinked POS purchases: {unlinked_pos}")
    print(f"Have matching receipts (date+amount): {matchable}")
    print(f"Truly missing receipts: {unlinked_pos - matchable}")
    print(f"\nMatch rate: {matchable/unlinked_pos*100:.1f}%")

    # Sample matchable ones
    cur.execute(
        f"""
        WITH pos AS (
            SELECT b.transaction_id, b.transaction_date, b.description, ABS({bt_amt}) AS amount
            FROM banking_transactions b
            WHERE b.receipt_id IS NULL
              AND ({bt_amt}) < 0
              AND ({like})
        )
        SELECT pos.transaction_id, pos.transaction_date, pos.description, pos.amount,
               r.id AS receipt_id, r.vendor_name, r.{rc_amount_col} AS receipt_amount
        FROM pos
        JOIN receipts r
          ON r.{rc_date_col}::date = pos.transaction_date::date
         AND ABS(COALESCE(r.{rc_amount_col}, 0) - pos.amount) <= 0.01
        ORDER BY pos.transaction_date DESC
        LIMIT 10
        """,
        params
    )
    samples = cur.fetchall()
    
    if samples:
        print('\nSample matches (POS ↔ Receipt):')
        for s in samples:
            print(f"  {s['transaction_date']} | POS: {s['description'][:40]} ${s['amount']:.2f}")
            print(f"    → Receipt {s['receipt_id']}: {s['vendor_name']} ${s['receipt_amount']:.2f}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
