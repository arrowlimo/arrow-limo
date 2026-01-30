"""
Delete duplicate 2025 bank fee receipts.

ISSUE: 39 duplicate bank fee receipts exist with same date + vendor + amount.
Pattern: Branch Transaction SERVICE CHARGE, ACC FEE, OVERDRAFT FEE, WITHDRAWAL
duplicated across different import sources.

SOLUTION: Keep oldest receipt (lowest receipt_id), delete newer duplicates.
"""

import psycopg2
import sys
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def find_duplicates():
    """Find duplicate bank fee receipts in 2025."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("FINDING DUPLICATE 2025 BANK FEE RECEIPTS")
    print("=" * 100)
    
    # Find duplicates by date + vendor + amount
    cur.execute("""
        SELECT 
            receipt_date, 
            vendor_name, 
            gross_amount, 
            COUNT(*) as dup_count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids,
            MIN(receipt_id) as keep_id
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2025
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, gross_amount DESC
    """)
    
    duplicates = cur.fetchall()
    print(f"\nFound {len(duplicates)} duplicate groups")
    print(f"Total duplicate receipts to delete: {sum(row[3] - 1 for row in duplicates)}")
    
    print("\nDuplicate groups:")
    for i, row in enumerate(duplicates, 1):
        date, vendor, amount, count, all_ids, keep_id = row
        delete_ids = all_ids[1:]  # All except first (lowest ID)
        vendor_short = vendor[:50] if vendor else 'None'
        print(f"\n{i}. {date} | {vendor_short}")
        print(f"   Amount: ${amount:.2f} | Count: {count}")
        print(f"   Keep ID: {keep_id}")
        print(f"   Delete IDs: {delete_ids}")
    
    cur.close()
    conn.close()
    
    return duplicates

def delete_duplicates(dry_run=True):
    """Delete duplicate receipts, keeping the oldest (lowest ID)."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
    else:
        print("EXECUTING DELETION")
    print("=" * 100)
    
    try:
        # Get duplicates
        cur.execute("""
            SELECT 
                receipt_date, 
                vendor_name, 
                gross_amount, 
                ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = 2025
            GROUP BY receipt_date, vendor_name, gross_amount
            HAVING COUNT(*) > 1
            ORDER BY receipt_date
        """)
        
        duplicates = cur.fetchall()
        all_delete_ids = []
        
        for date, vendor, amount, ids in duplicates:
            # Keep first ID, delete rest
            keep_id = ids[0]
            delete_ids = ids[1:]
            all_delete_ids.extend(delete_ids)
            
            vendor_short = vendor[:40] if vendor else 'None'
            print(f"\n{date} | {vendor_short} | ${amount:.2f}")
            print(f"  Keep: {keep_id}, Delete: {delete_ids}")
        
        print(f"\n{'=' * 100}")
        print(f"Total receipts to delete: {len(all_delete_ids)}")
        
        if not dry_run:
            # Create backup
            print("\nCreating backup...")
            backup_name = create_backup_before_delete(
                cur,
                'receipts',
                f"receipt_id IN ({','.join(map(str, all_delete_ids))})"
            )
            print(f"Backup created: {backup_name}")
            
            # Delete banking links first
            print("\nDeleting banking-receipt links...")
            cur.execute("""
                DELETE FROM banking_receipt_matching_ledger
                WHERE receipt_id = ANY(%s)
            """, (all_delete_ids,))
            print(f"Deleted {cur.rowcount} links")
            
            # Delete receipts
            print("\nDeleting duplicate receipts...")
            cur.execute("""
                DELETE FROM receipts
                WHERE receipt_id = ANY(%s)
            """, (all_delete_ids,))
            deleted_count = cur.rowcount
            print(f"Deleted {deleted_count} receipts")
            
            # Log the deletion
            log_deletion_audit(
                'receipts',
                deleted_count,
                f"Duplicate 2025 bank fees: IDs {all_delete_ids[:10]}..."
            )
            
            conn.commit()
            print("\n✓ Deletion completed successfully")
        else:
            print(f"\nWould delete {len(all_delete_ids)} receipts")
            conn.rollback()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    print("DELETE DUPLICATE 2025 BANK FEE RECEIPTS")
    print("=" * 100)
    print("\nThis script will remove duplicate bank fee receipts that have")
    print("identical date + vendor + amount combinations.")
    print("\nStrategy: Keep oldest receipt (lowest ID), delete duplicates")
    
    duplicates = find_duplicates()
    
    if '--write' in sys.argv:
        print("\n" + "=" * 100)
        response = input("\n⚠️  DELETE duplicate receipts? Type 'yes' to confirm: ")
        if response.lower() == 'yes':
            delete_duplicates(dry_run=False)
        else:
            print("Deletion cancelled.")
    else:
        print("\n" + "=" * 100)
        print("DRY RUN COMPLETE")
        print("\nTo delete duplicates, run:")
        print("  python l:\\limo\\scripts\\delete_duplicate_2025_bank_fees.py --write")
