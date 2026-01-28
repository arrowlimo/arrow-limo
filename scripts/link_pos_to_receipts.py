#!/usr/bin/env python3
"""
Link unlinked POS purchases to their matching receipts.

Based on diagnostic showing 100% match rate by date+amount.
"""

import os
import sys
import argparse
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
    parser = argparse.ArgumentParser(description='Link POS purchases to receipts')
    parser.add_argument('--write', action='store_true', help='Apply the linking (default is dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number of links to apply (for testing)')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    bt_cols = get_columns(cur, 'banking_transactions')
    rc_cols = get_columns(cur, 'receipts')
    
    bt_amt = amount_expr(bt_cols)
    
    # Find receipt columns
    rc_amount_col = 'gross_amount' if 'gross_amount' in rc_cols else ('amount' if 'amount' in rc_cols else None)
    rc_date_col = 'receipt_date' if 'receipt_date' in rc_cols else ('created_at' if 'created_at' in rc_cols else None)
    rc_pk = 'id' if 'id' in rc_cols else 'receipt_id'

    if not rc_amount_col or not rc_date_col:
        print("ERROR: Could not find required columns in receipts table")
        sys.exit(1)

    # Build POS pattern condition
    like = ' OR '.join([f"LOWER(description) LIKE '%{p}%'" for p in POS_PATTERNS])

    print("=" * 80)
    print("POS TO RECEIPTS LINKING")
    print("=" * 80)

    # Find matching pairs
    cur.execute(f"""
        WITH pos AS (
            SELECT b.transaction_id, b.transaction_date, b.description, ABS({bt_amt}) AS amount
            FROM banking_transactions b
            WHERE b.receipt_id IS NULL
              AND ({bt_amt}) < 0
              AND ({like})
        ),
        matches AS (
            SELECT DISTINCT ON (pos.transaction_id)
                pos.transaction_id,
                pos.transaction_date,
                pos.description,
                pos.amount,
                r.{rc_pk} AS receipt_id,
                r.vendor_name,
                r.{rc_amount_col} AS receipt_amount
            FROM pos
            JOIN receipts r
              ON r.{rc_date_col}::date = pos.transaction_date::date
             AND ABS(COALESCE(r.{rc_amount_col}, 0) - pos.amount) <= 0.01
            ORDER BY pos.transaction_id, r.{rc_pk}
        )
        SELECT * FROM matches
        ORDER BY transaction_date DESC
        {f'LIMIT {args.limit}' if args.limit else ''}
    """)
    
    matches = cur.fetchall()
    
    print(f"Found {len(matches)} POS purchases with matching receipts")
    
    if matches:
        print(f"\nSample of matches:")
        for i, m in enumerate(matches[:10]):
            print(f"  {m['transaction_date']} | Banking {m['transaction_id']}: {m['description'][:50]} ${m['amount']:.2f}")
            print(f"    → Receipt {m['receipt_id']}: {m['vendor_name'][:50]} ${m['receipt_amount']:.2f}")
        
        if len(matches) > 10:
            print(f"  ... and {len(matches) - 10} more")
    
    if not args.write:
        print("\n[DRY RUN] Use --write to apply linking")
        cur.close()
        conn.close()
        return
    
    # Apply linking
    print(f"\n{'='*80}")
    print(f"APPLYING {len(matches)} LINKS...")
    print(f"{'='*80}")
    
    updated = 0
    for m in matches:
        cur.execute("""
            UPDATE banking_transactions
            SET receipt_id = %s
            WHERE transaction_id = %s
        """, (m['receipt_id'], m['transaction_id']))
        updated += cur.rowcount
    
    conn.commit()
    
    print(f"\n✓ Updated {updated} banking_transactions rows")
    print(f"✓ Linked {len(matches)} POS purchases to receipts")
    
    # Verify
    cur.execute(f"""
        SELECT COUNT(*) as remaining
        FROM banking_transactions b
        WHERE b.receipt_id IS NULL
          AND ({bt_amt}) < 0
          AND ({like})
    """)
    remaining = cur.fetchone()['remaining']
    
    print(f"\nRemaining unlinked POS purchases: {remaining}")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
