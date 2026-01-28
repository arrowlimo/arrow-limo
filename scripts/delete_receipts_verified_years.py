#!/usr/bin/env python3
"""
Step 1 (Updated): Handle foreign keys and delete receipts for verified years (2012-2017).
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
    print("STEP 1: DELETE RECEIPTS FOR VERIFIED YEARS (2012-2017)")
    print("="*70)
    
    # Count receipts to delete
    cur.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2017
    """)
    total_to_delete = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM receipts")
    total_before = cur.fetchone()[0]
    
    remaining = total_before - total_to_delete
    
    print(f"\nTotal receipts now: {total_before:,}")
    print(f"Receipts to DELETE (2012-2017): {total_to_delete:,}")
    print(f"Receipts remaining: {remaining:,}")
    
    # Check for foreign key references
    print("\n=== CHECKING FOREIGN KEY REFERENCES ===\n")
    
    cur.execute("""
        SELECT COUNT(DISTINCT bt.transaction_id)
        FROM banking_transactions bt
        JOIN receipts r ON r.receipt_id = bt.receipt_id
        WHERE EXTRACT(YEAR FROM r.receipt_date) BETWEEN 2012 AND 2017
    """)
    banking_refs = cur.fetchone()[0]
    print(f"Banking transactions referencing these receipts: {banking_refs:,}")
    
    if banking_refs > 0:
        print(f"→ Will NULL out receipt_id in {banking_refs:,} banking_transactions")
    
    print(f"\n{'='*70}")
    print("READY TO PROCEED?")
    print(f"{'='*70}")
    print(f"  1. NULL out {banking_refs:,} banking_transactions.receipt_id references")
    print(f"  2. DELETE {total_to_delete:,} receipts from 2012-2017")
    print(f"  3. Remaining: {remaining:,} receipts")
    print(f"{'='*70}\n")
    
    response = input("Type 'DELETE' to proceed: ")
    
    if response.strip().upper() == 'DELETE':
        print("\n📝 Step 1: Clearing foreign key references...")
        
        # First, clear the foreign key references
        cur.execute("""
            UPDATE banking_transactions bt
            SET receipt_id = NULL
            WHERE receipt_id IN (
                SELECT receipt_id FROM receipts
                WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2017
            )
        """)
        
        updated_count = cur.rowcount
        print(f"✅ Cleared {updated_count:,} banking_transactions.receipt_id references")
        
        print("\n🗑️  Step 2: Deleting receipts for years 2012-2017...")
        
        cur.execute("""
            DELETE FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) BETWEEN 2012 AND 2017
        """)
        
        deleted_count = cur.rowcount
        print(f"✅ Deleted {deleted_count:,} receipts")
        
        conn.commit()
        print("✅ Changes committed to database")
        
        # Verify
        cur.execute("SELECT COUNT(*) FROM receipts")
        final_count = cur.fetchone()[0]
        print(f"\n{'='*70}")
        print(f"Final receipt count: {final_count:,}")
        
        if final_count == remaining:
            print("✅ Count matches expected!")
        else:
            print(f"⚠️  WARNING: Expected {remaining:,} but got {final_count:,}")
        
        # Show year breakdown after deletion
        print(f"\n=== RECEIPTS BY YEAR (AFTER DELETION) ===\n")
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM receipt_date) as year,
                COUNT(*) as count
            FROM receipts
            WHERE receipt_date IS NOT NULL
            GROUP BY year
            ORDER BY year
        """)
        
        for row in cur.fetchall():
            year = int(row[0]) if row[0] else 0
            count = row[1]
            print(f"  {year}: {count:,}")
        
        print(f"\n✅ STEP 1 COMPLETE - Ready for Step 2 (rebuild from verified banking)")
        
    else:
        print("\n❌ Operation cancelled. No changes made.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
