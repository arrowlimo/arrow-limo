#!/usr/bin/env python3
"""
Step 3: Identify potential duplicates (QuickBooks 8362 account issue).
Mark receipts that appear to be duplicates based on date + amount.
"""
import psycopg2
from datetime import datetime
from collections import defaultdict

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*70)
    print("STEP 3: IDENTIFY POTENTIAL DUPLICATES")
    print("="*70)
    
    print("\nAnalyzing 8362 account transactions for duplicates...")
    print("(Duplicates = same date + same amount)\n")
    
    # Find all receipts linked to account 8362
    cur.execute("""
        SELECT COUNT(DISTINCT r.receipt_id)
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '8362'
    """)
    
    account_8362_count = cur.fetchone()[0]
    print(f"Receipts linked to account 8362: {account_8362_count:,}")
    
    # Find duplicates (same date + amount)
    print("\nFinding duplicate groups (same date + same gross_amount)...")
    
    cur.execute("""
        SELECT 
            receipt_date,
            gross_amount,
            COUNT(*) as dup_count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids
        FROM receipts
        WHERE receipt_date IS NOT NULL 
          AND gross_amount IS NOT NULL
          AND is_verified_banking IS NOT TRUE  -- Don't mark verified as duplicates
        GROUP BY receipt_date, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY dup_count DESC, receipt_date
    """)
    
    duplicate_groups = cur.fetchall()
    
    print(f"Found {len(duplicate_groups):,} duplicate groups\n")
    
    if len(duplicate_groups) > 0:
        print("Top 10 duplicate groups:")
        print(f"{'Date':<12} {'Amount':>12} {'Count':>8} {'Receipt IDs'}")
        print("-" * 70)
        
        for i, (date, amount, count, ids) in enumerate(duplicate_groups[:10]):
            ids_str = ', '.join(str(x) for x in ids[:5])
            if len(ids) > 5:
                ids_str += f", ... ({len(ids)} total)"
            print(f"{date} ${amount:>10,.2f} {count:>8} {ids_str}")
    
    # Mark all receipts in duplicate groups
    print(f"\nMarking receipts as potential duplicates...")
    
    total_marked = 0
    for date, amount, count, ids in duplicate_groups:
        # Mark all except the first one as potential duplicates
        for receipt_id in ids[1:]:  # Skip first, mark rest
            cur.execute("""
                UPDATE receipts
                SET potential_duplicate = TRUE
                WHERE receipt_id = %s
            """, (receipt_id,))
            total_marked += 1
    
    conn.commit()
    
    print(f"✅ Marked {total_marked:,} receipts as potential_duplicate = TRUE")
    print(f"   (Kept first occurrence of each duplicate group unmarked)")
    
    # Summary statistics
    print(f"\n{'='*70}")
    print("SUMMARY STATISTICS")
    print(f"{'='*70}\n")
    
    cur.execute("SELECT COUNT(*) FROM receipts WHERE is_verified_banking IS TRUE")
    verified_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM receipts WHERE potential_duplicate IS TRUE")
    duplicate_count = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM receipts WHERE is_verified_banking IS NOT TRUE AND potential_duplicate IS NOT TRUE")
    other_count = cur.fetchone()[0]
    
    print(f"  {'Verified Banking (Clean)':<35}: {verified_count:>10,}")
    print(f"  {'Other (OK)':<35}: {other_count:>10,}")
    print(f"  {'Potential Duplicate (Review)':<35}: {duplicate_count:>10,}")
    
    # Total
    cur.execute("SELECT COUNT(*) FROM receipts")
    total = cur.fetchone()[0]
    print(f"\n  {'TOTAL RECEIPTS':<35}: {total:>10,}")
    
    # 8362 specific duplicates
    print(f"\n{'='*70}")
    print("8362 ACCOUNT ANALYSIS")
    print(f"{'='*70}\n")
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN r.potential_duplicate THEN 'Potential Duplicate'
                ELSE 'Unique'
            END as status,
            COUNT(*) as count
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '8362'
        GROUP BY status
    """)
    
    for status, count in cur.fetchall():
        print(f"  {status:<25}: {count:>10,}")
    
    print(f"\n✅ STEP 3 COMPLETE")
    print(f"\nNext: Generate Excel report with all receipts categorized")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
