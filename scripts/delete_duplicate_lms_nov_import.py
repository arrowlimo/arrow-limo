"""
Delete duplicate LMS payments imported on Nov 11-13, 2025.

These payments duplicate the July 24 import which had different key formats.
The July 24 import is the legitimate one and should remain.

Safety measures:
- Backup before deletion
- Deletion audit logging
- Foreign key constraint handling (income_ledger, banking_payment_links, related_payment_id)
"""
import psycopg2
import argparse
from datetime import datetime
from table_protection import create_backup_before_delete, log_deletion_audit, protect_deletion

def delete_duplicate_lms_payments(dry_run=True, override_key=None):
    """Delete LMS payments that duplicate July 24 import."""
    
    # Check protection
    protect_deletion('payments', dry_run=dry_run, override_key=override_key)
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("DELETE DUPLICATE LMS PAYMENTS (Nov 11-13 Import)")
    print("=" * 80)
    
    # Find duplicates: LMS payments that match July 24 payments
    cur.execute("""
        SELECT 
            p_lms.payment_id,
            p_lms.reserve_number,
            p_lms.amount,
            p_lms.payment_date,
            p_lms.payment_key,
            p_lms.created_at,
            p_july.payment_id as july_payment_id,
            p_july.payment_key as july_payment_key
        FROM payments p_lms
        JOIN payments p_july ON 
            p_lms.reserve_number = p_july.reserve_number 
            AND p_lms.amount = p_july.amount
            AND p_lms.payment_date = p_july.payment_date
        WHERE p_lms.payment_key LIKE 'LMS:%'
        AND p_july.payment_key NOT LIKE 'LMS:%'
        AND p_july.payment_key NOT LIKE 'LMSDEP:%'
        AND p_july.created_at::date = '2025-07-24'
        ORDER BY p_lms.created_at
    """)
    
    duplicates = cur.fetchall()
    
    print(f"\nFound {len(duplicates):,} duplicate LMS payments")
    
    if len(duplicates) == 0:
        print("No duplicates to delete.")
        cur.close()
        conn.close()
        return
    
    # Show sample
    print("\nSample duplicates (first 10):")
    for i, dup in enumerate(duplicates[:10], 1):
        print(f"\n{i}. LMS Payment ID: {dup[0]}")
        print(f"   Reserve: {dup[1]}, Amount: ${dup[2]:,.2f}, Date: {dup[3]}")
        print(f"   LMS Key: {dup[4]} (created {dup[5]})")
        print(f"   Duplicates July Payment ID: {dup[6]} (Key: {dup[7]})")
    
    # Calculate totals
    total_amount = sum(d[2] for d in duplicates)
    print(f"\nTotal duplicate amount: ${total_amount:,.2f}")
    
    # Get payment IDs to delete
    payment_ids = [d[0] for d in duplicates]
    
    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - No changes made")
        print("=" * 80)
        print(f"\nWould delete {len(payment_ids):,} payments totaling ${total_amount:,.2f}")
        print("\nTo apply changes, run with:")
        print(f"  python {__file__} --write --override-key ALLOW_DELETE_PAYMENTS_{datetime.now().strftime('%Y%m%d')}")
        
        cur.close()
        conn.close()
        return
    
    # APPLY MODE
    print("\n" + "=" * 80)
    print("APPLYING DELETIONS")
    print("=" * 80)
    
    # Step 1: Create backup
    print("\nStep 1: Creating backup...")
    backup_name = create_backup_before_delete(
        cur, 
        'payments', 
        condition=f"payment_id IN ({','.join(map(str, payment_ids))})"
    )
    print(f"✓ Backup created: {backup_name}")
    
    # Step 2: Handle foreign key constraints
    print("\nStep 2: Handling foreign key constraints...")
    
    # Check income_ledger references
    cur.execute("""
        SELECT COUNT(*) FROM income_ledger 
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    income_ledger_count = cur.fetchone()[0]
    
    if income_ledger_count > 0:
        print(f"  Deleting {income_ledger_count:,} income_ledger references...")
        cur.execute("""
            DELETE FROM income_ledger 
            WHERE payment_id = ANY(%s)
        """, (payment_ids,))
        print(f"  ✓ Deleted {cur.rowcount:,} income_ledger rows")
    
    # Check banking_payment_links
    cur.execute("""
        SELECT COUNT(*) FROM banking_payment_links 
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    banking_links_count = cur.fetchone()[0]
    
    if banking_links_count > 0:
        print(f"  Deleting {banking_links_count:,} banking_payment_links...")
        cur.execute("""
            DELETE FROM banking_payment_links 
            WHERE payment_id = ANY(%s)
        """, (payment_ids,))
        print(f"  ✓ Deleted {cur.rowcount:,} banking_payment_links rows")
    
    # Check self-references in related_payment_id
    cur.execute("""
        SELECT COUNT(*) FROM payments 
        WHERE related_payment_id = ANY(%s)
    """, (payment_ids,))
    related_count = cur.fetchone()[0]
    
    if related_count > 0:
        print(f"  Nullifying {related_count:,} related_payment_id references...")
        cur.execute("""
            UPDATE payments 
            SET related_payment_id = NULL 
            WHERE related_payment_id = ANY(%s)
        """, (payment_ids,))
        print(f"  ✓ Nullified {cur.rowcount:,} related_payment_id references")
    
    # Step 3: Delete the duplicate payments
    print(f"\nStep 3: Deleting {len(payment_ids):,} duplicate payments...")
    cur.execute("""
        DELETE FROM payments 
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    deleted_count = cur.rowcount
    print(f"✓ Deleted {deleted_count:,} payments")
    
    # Step 4: Recalculate charter balances
    print("\nStep 4: Recalculating charter balances...")
    cur.execute("""
        WITH payment_sums AS (
            SELECT 
                reserve_number,
                ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = COALESCE(ps.actual_paid, 0),
            balance = c.total_amount_due - COALESCE(ps.actual_paid, 0)
        FROM payment_sums ps
        WHERE c.reserve_number = ps.reserve_number
    """)
    print(f"✓ Updated {cur.rowcount:,} charter balances")
    
    # Also zero out charters with no payments
    cur.execute("""
        UPDATE charters
        SET paid_amount = 0,
            balance = total_amount_due
        WHERE reserve_number NOT IN (
            SELECT DISTINCT reserve_number 
            FROM payments 
            WHERE reserve_number IS NOT NULL
        )
        AND (paid_amount != 0 OR balance != total_amount_due)
    """)
    if cur.rowcount > 0:
        print(f"✓ Zeroed {cur.rowcount:,} charters with no payments")
    
    # Step 5: Log deletion audit
    log_deletion_audit(
        'payments', 
        deleted_count, 
        condition=f"payment_key LIKE 'LMS:%' (duplicate of July 24 import)"
    )
    
    # Commit transaction
    conn.commit()
    
    print("\n" + "=" * 80)
    print("DELETION COMPLETE")
    print("=" * 80)
    print(f"\n✓ Deleted {deleted_count:,} duplicate LMS payments")
    print(f"✓ Total amount removed: ${total_amount:,.2f}")
    print(f"✓ Backup saved: {backup_name}")
    
    # Verify results
    print("\nVerifying results...")
    cur.execute("""
        SELECT COUNT(*), SUM(amount) 
        FROM payments 
        WHERE payment_key LIKE 'LMS:%'
    """)
    remaining = cur.fetchone()
    print(f"  Remaining LMS payments: {remaining[0]:,} totaling ${remaining[1]:,.2f}")
    
    cur.execute("""
        SELECT 
            COUNT(*) as overpaid_count,
            SUM(ABS(balance)) as total_overpaid
        FROM charters
        WHERE balance < 0
    """)
    overpaid = cur.fetchone()
    print(f"  Overpaid charters: {overpaid[0]:,} totaling ${overpaid[1]:,.2f} in credits")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Delete duplicate LMS payments')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--override-key', help='Override key for protected table deletion')
    args = parser.parse_args()
    
    delete_duplicate_lms_payments(dry_run=not args.write, override_key=args.override_key)
