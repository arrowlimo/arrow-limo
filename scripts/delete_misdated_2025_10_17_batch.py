"""
Delete misdated 2025-10-17 banking batch and associated receipts.

PROBLEM IDENTIFIED:
- 554 transactions imported on 2025-10-17 14:59:38, all dated 2025-10-17
- Actually 2012 CIBC transactions based on descriptions ("Sales May 2012", etc.)
- 2 ACE TRUCK RENTALS entries are duplicates of Scotia 903990106011 data
- Auto-generated receipts were created from these misdated transactions
- 4 duplicate ACE TRUCK receipts exist (2 from original import, 2 auto-generated)

SOLUTION:
1. Delete the 554 misdated banking transactions
2. Delete associated receipts that were auto-created from this batch
3. Remove banking_receipt_matching_ledger links
4. Keep backups for audit trail

This will clean up the 2025 receipts and prevent false 2025 financial data.
"""

import psycopg2
import sys
from datetime import datetime
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def analyze_impact():
    """Analyze what will be deleted."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("IMPACT ANALYSIS: 2025-10-17 Misdated Batch Deletion")
    print("=" * 100)
    
    # Count banking transactions
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE created_at::date = '2025-10-17'
        AND account_number = '0228362'
    """)
    
    bt_count, total_debit, total_credit = cur.fetchone()
    print(f"\n1. Banking transactions to delete: {bt_count}")
    print(f"   Total debits: ${total_debit:,.2f}")
    print(f"   Total credits: ${total_credit:,.2f}")
    
    # Check receipts created from these transactions
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts r
        JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        WHERE bt.created_at::date = '2025-10-17'
        AND bt.account_number = '0228362'
    """)
    
    receipt_count, receipt_total = cur.fetchone()
    print(f"\n2. Receipts linked to these transactions: {receipt_count}")
    if receipt_total:
        print(f"   Total amount: ${receipt_total:,.2f}")
    
    # Check for ACE TRUCK specifically
    cur.execute("""
        SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount
        FROM receipts r
        JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        WHERE bt.transaction_id IN (44400, 44662)
    """)
    
    ace_receipts = cur.fetchall()
    print(f"\n3. ACE TRUCK receipts linked to misdated transactions: {len(ace_receipts)}")
    for row in ace_receipts:
        print(f"   Receipt ID {row[0]} | {row[1]} | {row[2]} | ${row[3]}")
    
    # Check all ACE TRUCK receipts in 2025
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
               created_from_banking, mapped_bank_account_id
        FROM receipts
        WHERE UPPER(vendor_name) LIKE '%ACE TRUCK%'
        AND EXTRACT(YEAR FROM receipt_date) = 2025
        ORDER BY receipt_id
    """)
    
    all_ace_2025 = cur.fetchall()
    print(f"\n4. ALL ACE TRUCK receipts dated 2025: {len(all_ace_2025)}")
    for row in all_ace_2025:
        print(f"   ID {row[0]} | {row[1]} | ${row[3]} | Banking:{row[4]} | Acct:{row[5]}")
    
    # Check banking links
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_receipt_matching_ledger bm
        JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
        WHERE bt.created_at::date = '2025-10-17'
        AND bt.account_number = '0228362'
    """)
    
    link_count = cur.fetchone()[0]
    print(f"\n5. Banking-receipt links to delete: {link_count}")
    
    cur.close()
    conn.close()
    
    return bt_count, receipt_count, link_count

def delete_misdated_batch(dry_run=True):
    """Delete the misdated batch and associated data."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
    else:
        print("EXECUTING DELETION")
    print("=" * 100)
    
    try:
        # Step 1: Create backup of banking_transactions
        if not dry_run:
            print("\nStep 1: Creating backup...")
            backup_name = create_backup_before_delete(
                cur, 
                'banking_transactions', 
                "created_at::date = '2025-10-17' AND account_number = '0228362'"
            )
            print(f"  Backup created: {backup_name}")
        else:
            print("\nStep 1: Would create backup of banking_transactions")
        
        # Step 2: Delete banking-receipt links
        cur.execute("""
            SELECT bm.id
            FROM banking_receipt_matching_ledger bm
            JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
            WHERE bt.created_at::date = '2025-10-17'
            AND bt.account_number = '0228362'
        """)
        link_ids = [row[0] for row in cur.fetchall()]
        
        if not dry_run:
            print(f"\nStep 2: Deleting {len(link_ids)} banking-receipt links...")
            cur.execute("""
                DELETE FROM banking_receipt_matching_ledger
                WHERE id IN (
                    SELECT bm.id
                    FROM banking_receipt_matching_ledger bm
                    JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
                    WHERE bt.created_at::date = '2025-10-17'
                    AND bt.account_number = '0228362'
                )
            """)
            print(f"  Deleted {cur.rowcount} links")
        else:
            print(f"\nStep 2: Would delete {len(link_ids)} banking-receipt links")
        
        # Step 3: Get receipts to potentially delete
        cur.execute("""
            SELECT DISTINCT r.receipt_id, r.vendor_name, r.gross_amount, r.created_from_banking
            FROM receipts r
            JOIN banking_receipt_matching_ledger bm ON r.receipt_id = bm.receipt_id
            JOIN banking_transactions bt ON bt.transaction_id = bm.banking_transaction_id
            WHERE bt.created_at::date = '2025-10-17'
            AND bt.account_number = '0228362'
        """)
        receipts_to_check = cur.fetchall()
        
        print(f"\nStep 3: Checking {len(receipts_to_check)} receipts...")
        receipts_to_delete = []
        
        for receipt_id, vendor, amount, from_banking in receipts_to_check:
            # Only delete if created_from_banking=True and no other links
            if from_banking:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM banking_receipt_matching_ledger
                    WHERE receipt_id = %s
                """, (receipt_id,))
                remaining_links = cur.fetchone()[0]
                
                if remaining_links == 0:
                    receipts_to_delete.append((receipt_id, vendor, amount))
        
        if not dry_run and receipts_to_delete:
            print(f"  Deleting {len(receipts_to_delete)} auto-generated receipts...")
            for rid, vendor, amount in receipts_to_delete:
                print(f"    Receipt {rid}: {vendor} ${amount}")
            
            receipt_ids = [r[0] for r in receipts_to_delete]
            cur.execute("""
                DELETE FROM receipts
                WHERE receipt_id = ANY(%s)
            """, (receipt_ids,))
            print(f"  Deleted {cur.rowcount} receipts")
        else:
            print(f"  Would delete {len(receipts_to_delete)} auto-generated receipts:")
            for rid, vendor, amount in receipts_to_delete[:10]:
                print(f"    Receipt {rid}: {vendor} ${amount}")
            if len(receipts_to_delete) > 10:
                print(f"    ... and {len(receipts_to_delete) - 10} more")
        
        # Step 4: Delete banking transactions
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE created_at::date = '2025-10-17'
            AND account_number = '0228362'
        """)
        bt_count = cur.fetchone()[0]
        
        if not dry_run:
            print(f"\nStep 4: Deleting {bt_count} banking transactions...")
            cur.execute("""
                DELETE FROM banking_transactions
                WHERE created_at::date = '2025-10-17'
                AND account_number = '0228362'
            """)
            deleted_count = cur.rowcount
            print(f"  Deleted {deleted_count} banking transactions")
            
            # Log the deletion
            log_deletion_audit(
                'banking_transactions',
                deleted_count,
                "created_at::date = '2025-10-17' AND account_number = '0228362'"
            )
            
            conn.commit()
            print("\n✓ Deletion completed successfully")
        else:
            print(f"\nStep 4: Would delete {bt_count} banking transactions")
            conn.rollback()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    print("DELETE MISDATED 2025-10-17 BANKING BATCH")
    print("=" * 100)
    print("\nThis script will remove 554 misdated banking transactions and")
    print("associated auto-generated receipts that were incorrectly dated 2025-10-17")
    print("but actually contain 2012 CIBC transaction data.")
    
    bt_count, receipt_count, link_count = analyze_impact()
    
    print("\n" + "=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print(f"  Banking transactions: {bt_count}")
    print(f"  Receipt links: {link_count}")
    print(f"  Receipts to review: {receipt_count}")
    
    # Check if --write flag provided
    if '--write' in sys.argv:
        print("\n" + "=" * 100)
        response = input("\n⚠️  ARE YOU SURE you want to delete these records? Type 'yes' to confirm: ")
        if response.lower() == 'yes':
            delete_misdated_batch(dry_run=False)
        else:
            print("Deletion cancelled.")
    else:
        print("\n" + "=" * 100)
        print("DRY RUN COMPLETE")
        print("\nTo actually delete these records, run:")
        print("  python l:\\limo\\scripts\\delete_misdated_2025_10_17_batch.py --write")
