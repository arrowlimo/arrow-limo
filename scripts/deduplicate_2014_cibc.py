#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Remove duplicate transactions from 2014 CIBC data.

For each duplicate group (same date, description, debit, credit),
keep the transaction with the lowest transaction_id and delete the rest.
"""

import sys
import psycopg2

def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    dry_run = '--write' not in sys.argv
    
    print("Remove 2014 CIBC Duplicate Transactions")
    print("=" * 70)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Find duplicates and identify which to delete
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                ROW_NUMBER() OVER (
                    PARTITION BY transaction_date, description, debit_amount, credit_amount
                    ORDER BY transaction_id
                ) as row_num
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = 2014
        )
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM duplicates
        WHERE row_num > 1
        ORDER BY transaction_date, transaction_id
    """)
    
    to_delete = cur.fetchall()
    
    if not to_delete:
        print("✓ No duplicates to remove")
        conn.close()
        return
    
    print(f"Found {len(to_delete)} duplicate transactions to remove")
    
    # Show sample
    print("\nSample duplicates to delete:")
    for row in to_delete[:10]:
        tid, date, desc, debit, credit = row
        print(f"  ID {tid}: {date} {desc[:40]:40s} D:{debit:>8.2f} C:{credit:>8.2f}")
    
    if len(to_delete) > 10:
        print(f"  ... and {len(to_delete) - 10} more")
    
    if dry_run:
        print("\n[DRY RUN] Would delete these duplicate transactions.")
        print("Run with --write to apply deletion.")
    else:
        print("\n[WRITE MODE] Deleting duplicates...")
        
        # Delete duplicates
        ids_to_delete = [row[0] for row in to_delete]
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE transaction_id = ANY(%s)
        """, (ids_to_delete,))
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"✓ Deleted {deleted_count} duplicate transactions")
        
        # Verify 2014 data
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT (transaction_date, description, debit_amount, credit_amount)) as unique_txns,
                SUM(debit_amount) as total_debits,
                SUM(credit_amount) as total_credits
            FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = 2014
        """)
        
        total, unique, debits, credits = cur.fetchone()
        
        print(f"\n2014 CIBC data after deduplication:")
        print(f"  Total transactions: {total}")
        print(f"  Unique transactions: {unique}")
        print(f"  Duplicates remaining: {total - unique}")
        print(f"  Total debits: ${debits:,.2f}")
        print(f"  Total credits: ${credits:,.2f}")
    
    conn.close()

if __name__ == '__main__':
    main()
