#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Clean up 2014 corrupted placeholder transactions.

After importing real transaction data from PDF statements, remove old
placeholder transactions with corrupted balances (< -100000).
"""

import sys
import psycopg2

def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    dry_run = '--write' not in sys.argv
    
    print("Clean up 2014 Corrupted Placeholder Transactions")
    print("=" * 70)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Find corrupted 2014 transactions
    cur.execute("""
        SELECT transaction_id, transaction_date, description, balance
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
        AND balance < -100000
        ORDER BY transaction_date
    """)
    
    corrupted = cur.fetchall()
    
    if not corrupted:
        print("✓ No corrupted 2014 placeholders found")
        conn.close()
        return
    
    print(f"Found {len(corrupted)} corrupted placeholder transactions")
    print("\nSample:")
    for row in corrupted[:10]:
        print(f"  {row[1]} {row[2][:50]:50s} Bal:{row[3]:,.2f}")
    if len(corrupted) > 10:
        print(f"  ... and {len(corrupted) - 10} more")
    
    if dry_run:
        print("\n[DRY RUN] Would delete these transactions.")
        print("Run with --write to apply deletion.")
    else:
        print("\n[WRITE MODE] Deleting corrupted placeholders...")
        
        # Delete corrupted transactions
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = 2014
            AND balance < -100000
        """)
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"✓ Deleted {deleted_count} corrupted placeholder transactions")
        
        # Verify 2014 data
        cur.execute("""
            SELECT COUNT(*), 
                   MIN(balance), MAX(balance),
                   SUM(debit_amount), SUM(credit_amount)
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = 2014
        """)
        count, min_bal, max_bal, total_debits, total_credits = cur.fetchone()
        
        print(f"\n2014 CIBC data after cleanup:")
        print(f"  Total transactions: {count}")
        print(f"  Balance range: ${min_bal:,.2f} to ${max_bal:,.2f}")
        print(f"  Total debits: ${total_debits:,.2f}")
        print(f"  Total credits: ${total_credits:,.2f}")
    
    conn.close()

if __name__ == '__main__':
    main()
