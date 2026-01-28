#!/usr/bin/env python3
"""
Normalize square_payment_id to match payment_key for Square payments.

Sets payments.square_payment_id = payments.payment_key where payment_method='credit_card'
and payment_key is not null, ensuring consistency with legacy Square queries.

Usage:
  python -X utf8 scripts/normalize_square_payment_id.py         # dry run
  python -X utf8 scripts/normalize_square_payment_id.py --write # apply
"""
import os
import sys
import psycopg2

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

def main():
    write = '--write' in sys.argv
    
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cur = conn.cursor()
    
    # Find Square payments where square_payment_id doesn't match payment_key
    cur.execute("""
        SELECT payment_id, payment_key, square_payment_id
        FROM payments
        WHERE payment_method = 'credit_card'
          AND payment_key IS NOT NULL
          AND (square_payment_id IS NULL OR square_payment_id != payment_key)
    """)
    
    rows = cur.fetchall()
    
    if not rows:
        print("✓ All Square payments already have square_payment_id = payment_key")
        cur.close()
        conn.close()
        return
    
    print(f"Found {len(rows)} Square payments to normalize")
    
    if write:
        cur.execute("""
            UPDATE payments
            SET square_payment_id = payment_key,
                last_updated = NOW()
            WHERE payment_method = 'credit_card'
              AND payment_key IS NOT NULL
              AND (square_payment_id IS NULL OR square_payment_id != payment_key)
        """)
        
        conn.commit()
        print(f"\n✓ COMMITTED: Updated {cur.rowcount} payments")
        print("  Set square_payment_id = payment_key for consistency")
    else:
        print(f"\nDRY RUN: Would update {len(rows)} payments")
        print("  Run with --write to apply")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
