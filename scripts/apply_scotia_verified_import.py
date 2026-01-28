#!/usr/bin/env python3
"""
Apply Scotia Bank 2012 verified data replacement.

This script:
1. Deletes existing Scotia Bank 2012 transactions (786 rows including 35 phantoms)
2. Removes associated payment links
3. Imports verified CSV data (759 rows)
4. Verifies the replacement
"""

import os
import sys
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

print("=" * 100)
print("APPLYING SCOTIA BANK 2012 VERIFIED DATA REPLACEMENT")
print("=" * 100)
print(f"\nTimestamp: {datetime.now()}")

conn = get_db_connection()
cur = conn.cursor()

try:
    # Step 1: Count existing data
    print("\n[1] Counting existing Scotia 2012 data...")
    
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions
        WHERE account_number = '903990106011'
          AND transaction_date >= '2012-01-01'
          AND transaction_date <= '2012-12-31'
    """)
    existing_count = cur.fetchone()[0]
    print(f"    Current database: {existing_count} transactions")
    
    cur.execute("SELECT COUNT(*) FROM staging_scotia_2012_verified")
    staged_count = cur.fetchone()[0]
    print(f"    Staged verified: {staged_count} transactions")
    print(f"    Net change: {staged_count - existing_count:+d} transactions")
    
    # Step 2: Delete payment links first (foreign key constraint)
    print("\n[2] Removing payment links...")
    
    cur.execute("""
        DELETE FROM banking_payment_links
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = '903990106011'
              AND transaction_date >= '2012-01-01'
              AND transaction_date <= '2012-12-31'
        )
    """)
    links_deleted = cur.rowcount
    print(f"    Deleted {links_deleted} payment link(s)")
    
    # Step 3: Delete existing Scotia 2012 transactions
    print("\n[3] Deleting existing Scotia 2012 transactions...")
    
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = '903990106011'
          AND transaction_date >= '2012-01-01'
          AND transaction_date <= '2012-12-31'
    """)
    deleted_count = cur.rowcount
    print(f"    Deleted {deleted_count} transactions")
    
    # Step 4: Insert verified data from staging
    print("\n[4] Inserting verified data...")
    
    # Get the absolute maximum transaction_id to avoid ALL conflicts
    cur.execute("SELECT COALESCE(MAX(transaction_id), 0) FROM banking_transactions")
    max_id = cur.fetchone()[0]
    next_id = max_id + 1
    
    print(f"    Starting from transaction ID: {next_id}")
    
    cur.execute("""
        SELECT 
            csv_transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            source_hash
        FROM staging_scotia_2012_verified
        ORDER BY transaction_date, staging_id
    """)
    
    staged_data = cur.fetchall()
    
    # Prepare insert data with completely new sequential IDs
    insert_values = []
    for row in staged_data:
        csv_id, trans_date, desc, debit, credit, source_hash = row
        
        insert_values.append((
            next_id,  # Use new sequential ID
            '903990106011',  # account_number
            trans_date,
            desc,
            debit,
            credit,
            None,  # balance (will be recalculated)
            None,  # category
            'scotiabank_verified_data.csv',  # source_file
            source_hash,
            datetime.now()  # created_at
        ))
        next_id += 1
    
    # Insert with new transaction IDs
    execute_values(cur, """
        INSERT INTO banking_transactions 
            (transaction_id, account_number, transaction_date, description, 
             debit_amount, credit_amount, balance, category, source_file, 
             source_hash, created_at)
        VALUES %s
    """, insert_values)
    
    inserted_count = cur.rowcount
    print(f"    Inserted {inserted_count} transactions")
    print(f"    New ID range: {max_id + 1} to {next_id - 1}")
    
    # Step 5: Verify insertion
    print("\n[5] Verifying replacement...")
    
    cur.execute("""
        SELECT 
            MIN(transaction_id) as min_id,
            MAX(transaction_id) as max_id,
            COUNT(*) as count,
            MIN(transaction_date) as min_date,
            MAX(transaction_date) as max_date,
            SUM(debit_amount) as total_debit,
            SUM(credit_amount) as total_credit
        FROM banking_transactions
        WHERE account_number = '903990106011'
          AND transaction_date >= '2012-01-01'
          AND transaction_date <= '2012-12-31'
    """)
    
    verify = cur.fetchone()
    
    print(f"\n    New Scotia 2012 data:")
    print(f"      Transaction IDs: {verify[0]} to {verify[1]}")
    print(f"      Count: {verify[2]}")
    print(f"      Date range: {verify[3]} to {verify[4]}")
    print(f"      Total debits: ${verify[5]:,.2f}")
    print(f"      Total credits: ${verify[6]:,.2f}")
    print(f"      Net: ${(verify[6] or 0) - (verify[5] or 0):,.2f}")
    
    # Commit the transaction
    print("\n[6] Committing changes...")
    conn.commit()
    print("    ✓ Changes committed successfully")
    
    print("\n" + "=" * 100)
    print("REPLACEMENT COMPLETE")
    print("=" * 100)
    print(f"\nSummary:")
    print(f"  Deleted: {deleted_count} transactions (including 35 phantom entries)")
    print(f"  Inserted: {inserted_count} verified transactions")
    print(f"  Net change: {inserted_count - deleted_count:+d} transactions")
    print(f"  Payment links removed: {links_deleted}")
    
    print(f"\nNext step: Run receipts matching")
    
except Exception as e:
    print(f"\n[FAIL] ERROR: {e}")
    print("\nRolling back changes...")
    conn.rollback()
    print("✓ Rollback complete - database unchanged")
    sys.exit(1)
    
finally:
    cur.close()
    conn.close()
