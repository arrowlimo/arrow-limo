"""
Analyze and delete remaining duplicate payments from August 5 and October 13, 2025 imports.

After removing Nov 11-13 LMS duplicates, there are still ~639 charters with 2x payments.
These appear to be from other import batches that also created duplicates.
"""
import psycopg2
import argparse
from datetime import datetime
from table_protection import create_backup_before_delete, log_deletion_audit, protect_deletion

def analyze_remaining_duplicates(dry_run=True, override_key=None):
    """Find and delete remaining duplicate payments from Aug 5 and Oct 13 imports."""
    
    if not dry_run:
        protect_deletion('payments', dry_run=dry_run, override_key=override_key)
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("ANALYZE REMAINING DUPLICATE PAYMENTS")
    print("=" * 80)
    
    # Find charters with approximately 2x payments
    cur.execute("""
        WITH payment_totals AS (
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.total_amount_due,
                c.paid_amount,
                c.balance,
                COUNT(p.payment_id) as payment_count
            FROM charters c
            LEFT JOIN payments p ON p.reserve_number = c.reserve_number
            WHERE c.total_amount_due > 0
            GROUP BY c.charter_id, c.reserve_number, c.total_amount_due, 
                     c.paid_amount, c.balance
        )
        SELECT 
            reserve_number,
            total_amount_due,
            paid_amount,
            balance,
            payment_count
        FROM payment_totals
        WHERE ABS(paid_amount - (total_amount_due * 2)) < 1.0
        AND payment_count >= 2
        ORDER BY total_amount_due DESC
        LIMIT 20
    """)
    
    doubled_charters = cur.fetchall()
    print(f"\nFound {len(doubled_charters)} sample charters with 2x payments:")
    
    for charter in doubled_charters[:10]:
        print(f"\nReserve: {charter[0]}")
        print(f"  Total Due: ${charter[1]:,.2f}, Paid: ${charter[2]:,.2f}, Balance: ${charter[3]:,.2f}")
        print(f"  Payment Count: {charter[4]}")
        
        # Show payment details
        cur.execute("""
            SELECT payment_id, amount, payment_date, payment_key, created_at
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date, created_at
        """, (charter[0],))
        
        payments = cur.fetchall()
        for p in payments:
            print(f"    Payment {p[0]}: ${p[1]:,.2f} on {p[2]}, Key: {p[3]}, Created: {p[4]}")
    
    # Identify duplicate patterns by created_at date
    print("\n" + "=" * 80)
    print("DUPLICATE PATTERNS BY IMPORT DATE")
    print("=" * 80)
    
    cur.execute("""
        WITH duplicate_pairs AS (
            SELECT 
                p1.payment_id as payment_id_1,
                p1.reserve_number,
                p1.amount,
                p1.payment_date,
                p1.payment_key as key_1,
                p1.created_at::date as created_1,
                p2.payment_id as payment_id_2,
                p2.payment_key as key_2,
                p2.created_at::date as created_2
            FROM payments p1
            JOIN payments p2 ON 
                p1.reserve_number = p2.reserve_number 
                AND p1.amount = p2.amount
                AND p1.payment_date = p2.payment_date
                AND p1.payment_id < p2.payment_id
            WHERE p1.payment_key IS DISTINCT FROM p2.payment_key
        )
        SELECT 
            created_2 as duplicate_import_date,
            COUNT(*) as duplicate_count,
            SUM(amount) as total_amount
        FROM duplicate_pairs
        GROUP BY created_2
        ORDER BY duplicate_count DESC
    """)
    
    import_dates = cur.fetchall()
    print("\nDuplicate payments by import date:")
    for row in import_dates:
        print(f"  {row[0]}: {row[1]:,} duplicates, ${row[2]:,.2f}")
    
    # Find specific duplicates to delete
    print("\n" + "=" * 80)
    print("IDENTIFYING DUPLICATES TO DELETE")
    print("=" * 80)
    
    # Strategy: Keep the EARLIEST payment_id (original), delete higher IDs (duplicates)
    # Also handle remaining LMS duplicates that weren't caught
    cur.execute("""
        WITH duplicate_pairs AS (
            SELECT 
                p1.payment_id as keep_id,
                p1.payment_key as keep_key,
                p2.payment_id as delete_id,
                p2.reserve_number,
                p2.amount,
                p2.payment_date,
                p2.payment_key as delete_key,
                p2.created_at as delete_created
            FROM payments p1
            JOIN payments p2 ON 
                p1.reserve_number = p2.reserve_number 
                AND p1.amount = p2.amount
                AND p1.payment_date = p2.payment_date
                AND p1.payment_id < p2.payment_id  -- Keep lower ID, delete higher ID
            WHERE p1.payment_key IS DISTINCT FROM p2.payment_key
            -- Include both non-LMS and remaining LMS duplicates
        )
        SELECT 
            delete_id,
            reserve_number,
            amount,
            payment_date,
            delete_key as payment_key,
            delete_created
        FROM duplicate_pairs
        ORDER BY delete_created, reserve_number
    """)
    
    duplicates = cur.fetchall()
    print(f"\nFound {len(duplicates):,} duplicate payments to delete")
    
    if len(duplicates) == 0:
        print("No duplicates found to delete.")
        cur.close()
        conn.close()
        return
    
    # Show sample
    print("\nSample duplicates (first 10):")
    for i, dup in enumerate(duplicates[:10], 1):
        print(f"\n{i}. Payment ID: {dup[0]}")
        print(f"   Reserve: {dup[1]}, Amount: ${dup[2]:,.2f}, Date: {dup[3]}")
        print(f"   Key: {dup[4]}, Created: {dup[5]}")
    
    total_amount = sum(d[2] for d in duplicates)
    payment_ids = [d[0] for d in duplicates]
    
    print(f"\nTotal to delete: {len(payment_ids):,} payments, ${total_amount:,.2f}")
    
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
        condition=f"Duplicates from Aug 5, Aug 9, Oct 13 imports"
    )
    
    # Commit transaction
    conn.commit()
    
    print("\n" + "=" * 80)
    print("DELETION COMPLETE")
    print("=" * 80)
    print(f"\n✓ Deleted {deleted_count:,} duplicate payments")
    print(f"✓ Total amount removed: ${total_amount:,.2f}")
    print(f"✓ Backup saved: {backup_name}")
    
    # Verify results
    print("\nVerifying results...")
    cur.execute("""
        SELECT 
            COUNT(*) as overpaid_count,
            SUM(ABS(balance)) as total_overpaid
        FROM charters
        WHERE balance < 0
    """)
    overpaid = cur.fetchone()
    print(f"  Overpaid charters: {overpaid[0]:,} totaling ${overpaid[1]:,.2f} in credits")
    
    cur.execute("""
        WITH payment_totals AS (
            SELECT 
                c.charter_id,
                c.total_amount_due,
                c.paid_amount
            FROM charters c
            WHERE c.total_amount_due > 0
        )
        SELECT COUNT(*)
        FROM payment_totals
        WHERE ABS(paid_amount - (total_amount_due * 2)) < 1.0
    """)
    remaining_doubles = cur.fetchone()[0]
    print(f"  Remaining 2x duplicates: {remaining_doubles:,}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Delete remaining duplicate payments from Aug/Oct imports')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--override-key', help='Override key for protected table deletion')
    args = parser.parse_args()
    
    analyze_remaining_duplicates(dry_run=not args.write, override_key=args.override_key)
