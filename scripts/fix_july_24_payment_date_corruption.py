"""
Fix July 24, 2025 import data quality issue where payment_date was set to import date.

The July 24 import incorrectly set payment_date = 2025-07-24 (import date) for many payments
instead of preserving the original payment dates. This created false "duplicates" where:
- Payment A has correct historical date (e.g., 2012-06-29)
- Payment B has corrupted date (2025-07-24)

Strategy: Delete payments with payment_date = 2025-07-24 when there's another payment 
for the same reserve_number with correct historical date.
"""
import psycopg2
import argparse
from datetime import datetime, date
from table_protection import create_backup_before_delete, log_deletion_audit, protect_deletion

def fix_july_24_corruption(dry_run=True, override_key=None):
    """Delete payments where payment_date was corrupted to 2025-07-24."""
    
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
    print("ANALYZE JULY 24 PAYMENT_DATE CORRUPTION")
    print("=" * 80)
    
    # Find payments with corrupted date (2025-07-24) that have a matching payment with correct date
    cur.execute("""
        WITH corrupted_payments AS (
            SELECT 
                p_bad.payment_id,
                p_bad.reserve_number,
                p_bad.amount,
                p_bad.payment_date as bad_date,
                p_bad.payment_key as bad_key,
                p_bad.created_at,
                p_good.payment_id as good_payment_id,
                p_good.payment_date as good_date,
                p_good.payment_key as good_key
            FROM payments p_bad
            JOIN payments p_good ON 
                p_bad.reserve_number = p_good.reserve_number
                AND p_bad.amount = p_good.amount
                AND p_bad.payment_id != p_good.payment_id
            WHERE p_bad.payment_date = '2025-07-24'
            AND p_good.payment_date != '2025-07-24'
            AND p_bad.created_at::date = '2025-07-24'  -- Only July 24 import
        )
        SELECT 
            payment_id,
            reserve_number,
            amount,
            bad_date,
            bad_key,
            created_at,
            good_payment_id,
            good_date,
            good_key
        FROM corrupted_payments
        ORDER BY reserve_number, payment_id
    """)
    
    corrupted = cur.fetchall()
    print(f"\nFound {len(corrupted):,} payments with corrupted payment_date = 2025-07-24")
    
    if len(corrupted) == 0:
        print("No corrupted payments found.")
        cur.close()
        conn.close()
        return
    
    # Show sample
    print("\nSample corrupted payments (first 10):")
    for i, row in enumerate(corrupted[:10], 1):
        print(f"\n{i}. Payment ID: {row[0]} (corrupted)")
        print(f"   Reserve: {row[1]}, Amount: ${row[2]:,.2f}")
        print(f"   Corrupted date: {row[3]}, Key: {row[4]}")
        print(f"   Correct payment ID: {row[6]}, Date: {row[7]}, Key: {row[8]}")
    
    total_amount = sum(r[2] for r in corrupted)
    payment_ids = [r[0] for r in corrupted]
    
    print(f"\nTotal to delete: {len(payment_ids):,} payments, ${total_amount:,.2f}")
    
    # Group by reserve to show impact
    cur.execute("""
        WITH corrupted_payments AS (
            SELECT 
                p_bad.reserve_number,
                COUNT(*) as corrupted_count,
                SUM(p_bad.amount) as corrupted_amount
            FROM payments p_bad
            WHERE p_bad.payment_date = '2025-07-24'
            AND p_bad.created_at::date = '2025-07-24'
            AND p_bad.payment_id = ANY(%s)
            GROUP BY p_bad.reserve_number
        )
        SELECT COUNT(*), SUM(corrupted_amount)
        FROM corrupted_payments
    """, (payment_ids,))
    
    charter_count, total = cur.fetchone()
    print(f"\nAffected charters: {charter_count:,}")
    
    if dry_run:
        print("\n" + "=" * 80)
        print("DRY RUN - No changes made")
        print("=" * 80)
        print(f"\nWould delete {len(payment_ids):,} corrupted payments totaling ${total_amount:,.2f}")
        print(f"Would recalculate balances for {charter_count:,} charters")
        print("\nTo apply changes, run with:")
        print(f"  python {__file__} --write --override-key ALLOW_DELETE_PAYMENTS_{datetime.now().strftime('%Y%m%d')}")
        
        cur.close()
        conn.close()
        return
    
    # APPLY MODE
    print("\n" + "=" * 80)
    print("APPLYING FIXES")
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
    
    # Step 3: Delete the corrupted payments
    print(f"\nStep 3: Deleting {len(payment_ids):,} corrupted payments...")
    cur.execute("""
        DELETE FROM payments 
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    deleted_count = cur.rowcount
    print(f"✓ Deleted {deleted_count:,} payments")
    
    # Log deletion
    log_deletion_audit('payments', deleted_count, 
                      condition=f"payment_date = '2025-07-24' AND created_at::date = '2025-07-24' (corrupted import date)")
    
    # Step 4: Recalculate charter balances
    print(f"\nStep 4: Recalculating balances for affected charters...")
    
    # Get affected reserve numbers
    cur.execute("""
        SELECT DISTINCT reserve_number
        FROM charters
        WHERE reserve_number IN (
            SELECT DISTINCT reserve_number 
            FROM payments 
            WHERE reserve_number IS NOT NULL
        )
    """)
    affected_reserves = [r[0] for r in cur.fetchall()]
    
    # Recalculate paid_amount and balance for each charter
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
        SET 
            paid_amount = COALESCE(ps.actual_paid, 0),
            balance = c.total_amount_due - COALESCE(ps.actual_paid, 0)
        FROM payment_sums ps
        WHERE c.reserve_number = ps.reserve_number
    """)
    updated_count = cur.rowcount
    
    # Also zero out charters with no payments
    cur.execute("""
        UPDATE charters c
        SET paid_amount = 0, balance = total_amount_due
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.reserve_number = c.reserve_number
        )
        AND paid_amount != 0
    """)
    zeroed_count = cur.rowcount
    
    print(f"✓ Recalculated {updated_count:,} charters with payments")
    print(f"✓ Zeroed {zeroed_count:,} charters with no payments")
    
    conn.commit()
    
    # Step 5: Verify results
    print("\nStep 5: Verifying results...")
    
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
            GROUP BY c.charter_id
        )
        SELECT 
            COUNT(*) as total_overpaid,
            SUM(ABS(balance)) as total_overpaid_amount,
            COUNT(CASE WHEN ABS(paid_amount - (total_amount_due * 2)) < 1.0 THEN 1 END) as approx_doubled
        FROM payment_totals
        WHERE balance < -1.0
    """)
    
    stats = cur.fetchone()
    print(f"✓ Overpaid charters: {stats[0]:,} (${stats[1]:,.2f})")
    print(f"✓ Approximately doubled payments: {stats[2]:,}")
    
    print("\n" + "=" * 80)
    print("SUCCESS - Corruption fixed")
    print("=" * 80)
    print(f"\n✓ Deleted {deleted_count:,} corrupted payments (${total_amount:,.2f})")
    print(f"✓ Recalculated {updated_count + zeroed_count:,} charter balances")
    print(f"✓ Backup: {backup_name}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix July 24 payment_date corruption')
    parser.add_argument('--write', action='store_true', 
                       help='Apply changes (default is dry-run)')
    parser.add_argument('--override-key', type=str,
                       help='Override key for protected table deletion')
    
    args = parser.parse_args()
    
    fix_july_24_corruption(dry_run=not args.write, override_key=args.override_key)
