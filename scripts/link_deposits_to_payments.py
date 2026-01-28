#!/usr/bin/env python3
"""
Link banking deposits to payment records where they match by date and amount.

Based on audit showing 884 matchable deposits.
Uses banking_payment_links table for non-destructive linking.
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


def main():
    parser = argparse.ArgumentParser(description='Link deposits to payments')
    parser.add_argument('--write', action='store_true', help='Apply the linking (default is dry-run)')
    parser.add_argument('--tolerance', type=float, default=0.01, help='Amount tolerance (default: $0.01)')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("DEPOSIT TO PAYMENT LINKING")
    print("=" * 80)

    # Create link table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS banking_payment_links (
            banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
            payment_id INTEGER REFERENCES payments(payment_id),
            link_confidence DECIMAL(3,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (banking_transaction_id, payment_id)
        )
    """)

    # Find matching pairs (deposits to payments, exact date + amount within tolerance)
    cur.execute(f"""
        WITH deposits AS (
            SELECT 
                bt.transaction_id,
                bt.transaction_date,
                bt.description,
                bt.credit_amount
            FROM banking_transactions bt
            WHERE bt.credit_amount > 0
              AND NOT EXISTS (
                  SELECT 1 FROM banking_payment_links bpl 
                  WHERE bpl.banking_transaction_id = bt.transaction_id
              )
        ),
        matches AS (
            SELECT DISTINCT ON (d.transaction_id)
                d.transaction_id,
                d.transaction_date,
                d.description,
                d.credit_amount,
                p.payment_id,
                p.account_number,
                p.amount,
                p.payment_method,
                ABS(d.credit_amount - p.amount) as diff
            FROM deposits d
            JOIN payments p 
              ON p.payment_date::date = d.transaction_date::date
             AND ABS(p.amount - d.credit_amount) <= {args.tolerance}
            WHERE p.amount > 0
            ORDER BY d.transaction_id, ABS(d.credit_amount - p.amount)
        )
        SELECT * FROM matches
        ORDER BY transaction_date DESC
    """)
    
    matches = cur.fetchall()
    
    print(f"Found {len(matches)} matchable deposit→payment pairs")
    
    if matches:
        print(f"\nSample matches:")
        for i, m in enumerate(matches[:10]):
            print(f"  {m['transaction_date']} | Banking {m['transaction_id']}: {m['description'][:40]} ${m['credit_amount']:.2f}")
            print(f"    → Payment {m['payment_id']}: Account {m['account_number']} {m['payment_method']} ${m['amount']:.2f}")
        
        if len(matches) > 10:
            print(f"  ... and {len(matches) - 10} more")
        
        # Amount summary
        total_deposit = sum(m['credit_amount'] for m in matches)
        total_payment = sum(m['amount'] for m in matches)
        print(f"\nTotal deposits: ${total_deposit:,.2f}")
        print(f"Total payments: ${total_payment:,.2f}")
        print(f"Difference: ${abs(total_deposit - total_payment):,.2f}")
    
    if not args.write:
        print("\n[DRY RUN] Use --write to apply linking")
        cur.close()
        conn.close()
        return
    
    # Apply linking
    print(f"\n{'='*80}")
    print(f"APPLYING {len(matches)} LINKS...")
    print(f"{'='*80}")
    
    inserted = 0
    for m in matches:
        cur.execute("""
            INSERT INTO banking_payment_links 
                (banking_transaction_id, payment_id, link_confidence)
            VALUES (%s, %s, 1.0)
            ON CONFLICT (banking_transaction_id, payment_id) DO NOTHING
        """, (m['transaction_id'], m['payment_id']))
        inserted += cur.rowcount
    
    conn.commit()
    
    print(f"\n✓ Inserted {inserted} new deposit→payment links")
    
    # Verify
    cur.execute("""
        SELECT COUNT(DISTINCT banking_transaction_id) as linked_deposits
        FROM banking_payment_links
    """)
    linked = cur.fetchone()['linked_deposits']
    
    cur.execute("""
        SELECT COUNT(*) as total_deposits
        FROM banking_transactions
        WHERE credit_amount > 0
    """)
    total = cur.fetchone()['total_deposits']
    
    print(f"✓ Total deposits linked: {linked:,} / {total:,} ({linked/total*100:.1f}%)")
    
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
