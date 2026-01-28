#!/usr/bin/env python3
"""
Step 1: Analyze and delete receipts for verified years (2012-2017).
Then rebuild from verified banking sources only.
"""
import psycopg2
from datetime import datetime

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*70)
    print("STEP 1: ANALYZE RECEIPTS FOR VERIFIED YEARS (2012-2017)")
    print("="*70)
    
    # Count receipts by year
    print("\n=== RECEIPTS BY YEAR ===\n")
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as count
        FROM receipts
        WHERE receipt_date IS NOT NULL
        GROUP BY year
        ORDER BY year
    """)
    
    total_to_delete = 0
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else 0
        count = row[1]
        if 2012 <= year <= 2017:
            total_to_delete += count
            print(f"  {year}: {count:>8,} ← WILL DELETE")
        else:
            print(f"  {year}: {count:>8,}")
    
    # Count NULL dates
    cur.execute("SELECT COUNT(*) FROM receipts WHERE receipt_date IS NULL")
    null_count = cur.fetchone()[0]
    print(f"  NULL: {null_count:>8,}")
    
    # Total count
    cur.execute("SELECT COUNT(*) FROM receipts")
    total_before = cur.fetchone()[0]
    
    remaining = total_before - total_to_delete
    
    print(f"\n{'='*70}")
    print(f"Total receipts now: {total_before:,}")
    print(f"Receipts to DELETE (2012-2017): {total_to_delete:,}")
    print(f"Receipts remaining after delete: {remaining:,}")
    print(f"{'='*70}")
    
    # Show what verified banking we'll rebuild from
    print("\n=== VERIFIED BANKING SOURCES TO REBUILD FROM ===\n")
    
    cur.execute("""
        SELECT 
            source_file,
            MIN(transaction_date) as min_date,
            MAX(transaction_date) as max_date,
            COUNT(*) as transaction_count
        FROM banking_transactions
        WHERE source_file IN ('verified_2013_2014_scotia', 'CIBC_7461615_2012_2017_VERIFIED.xlsx')
        GROUP BY source_file
        ORDER BY source_file
    """)
    
    total_verified_banking = 0
    for row in cur.fetchall():
        source, min_date, max_date, count = row
        total_verified_banking += count
        print(f"  {source}")
        print(f"    Date range: {min_date} to {max_date}")
        print(f"    Transactions: {count:,}\n")
    
    print(f"Total verified banking transactions: {total_verified_banking:,}")
    print(f"These will create ~{total_verified_banking:,} new receipts")
    
    print(f"\n{'='*70}")
    print("READY TO PROCEED?")
    print(f"{'='*70}")
    print(f"  1. DELETE {total_to_delete:,} receipts from 2012-2017")
    print(f"  2. CREATE ~{total_verified_banking:,} receipts from verified banking")
    print(f"  3. Final count: ~{remaining + total_verified_banking:,} receipts")
    print(f"{'='*70}\n")
    
    response = input("Type 'DELETE' to proceed: ")
    
    if response.strip().upper() == 'DELETE':
        print("\n🗑️  Deleting receipts for years 2012-2017...")
        
        cur.execute("""
            DELETE FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2017
        """)
        
        deleted_count = cur.rowcount
        conn.commit()
        
        print(f"✅ Deleted {deleted_count:,} receipts")
        
        # Verify
        cur.execute("SELECT COUNT(*) FROM receipts")
        final_count = cur.fetchone()[0]
        print(f"✅ Remaining receipts: {final_count:,}")
        
        if final_count == remaining:
            print("✅ Count matches expected!")
        else:
            print(f"⚠️  WARNING: Expected {remaining:,} but got {final_count:,}")
    else:
        print("\n❌ Operation cancelled. No changes made.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
