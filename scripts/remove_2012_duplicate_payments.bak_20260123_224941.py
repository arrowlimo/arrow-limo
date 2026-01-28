"""
Remove 2012 QBO duplicate payments (keep one from each duplicate pair).

These are confirmed QBO import duplicates - identical date, amount, account.
We'll keep the payment with the LOWER payment_id (first imported) and delete the duplicate.

Usage:
  python remove_2012_duplicate_payments.py              # Dry run - show what would be deleted
  python remove_2012_duplicate_payments.py --write      # Apply deletions with backup
"""

import psycopg2
import argparse
from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    parser = argparse.ArgumentParser(description='Remove 2012 duplicate payments')
    parser.add_argument('--write', action='store_true', help='Apply deletions (with backup)')
    parser.add_argument('--override-key', help='Required override key for protected table deletion')
    args = parser.parse_args()
    
    # Table protection check
    protect_deletion('payments', dry_run=not args.write, override_key=args.override_key)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("2012 DUPLICATE PAYMENT REMOVAL - DRY RUN" if not args.write else "2012 DUPLICATE PAYMENT REMOVAL - APPLYING CHANGES")
    print("=" * 100)
    
    # Identify duplicates - keep LOWER payment_id (first imported)
    print("\nIdentifying duplicate payments...")
    print("-" * 100)
    
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                payment_id,
                payment_date,
                amount,
                account_number,
                payment_key,
                ROW_NUMBER() OVER (
                    PARTITION BY payment_date, amount, COALESCE(account_number, '')
                    ORDER BY payment_id
                ) as row_num
            FROM payments
            WHERE charter_id IS NULL
            AND EXTRACT(YEAR FROM payment_date) = 2012
            AND amount > 0
        )
        SELECT 
            payment_id,
            payment_date,
            amount,
            account_number,
            payment_key
        FROM duplicates
        WHERE row_num > 1
        ORDER BY amount DESC, payment_date
    """)
    
    to_delete = cur.fetchall()
    
    print(f"\nFound {len(to_delete)} duplicate payments to delete")
    
    if len(to_delete) == 0:
        print("No duplicates found - nothing to do!")
        cur.close()
        conn.close()
        return
    
    # Show statistics
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                payment_id,
                payment_date,
                amount,
                account_number,
                ROW_NUMBER() OVER (
                    PARTITION BY payment_date, amount, COALESCE(account_number, '')
                    ORDER BY payment_id
                ) as row_num
            FROM payments
            WHERE charter_id IS NULL
            AND EXTRACT(YEAR FROM payment_date) = 2012
            AND amount > 0
        )
        SELECT 
            COUNT(*) as total_payments,
            COUNT(DISTINCT CONCAT(payment_date::text, '|', amount::text, '|', COALESCE(account_number, ''))) as unique_combinations,
            COUNT(CASE WHEN row_num = 1 THEN 1 END) as payments_to_keep,
            COUNT(CASE WHEN row_num > 1 THEN 1 END) as payments_to_delete,
            SUM(CASE WHEN row_num > 1 THEN amount ELSE 0 END) as amount_to_delete
        FROM duplicates
    """)
    
    stats = cur.fetchone()
    print(f"\nStatistics:")
    print(f"  Total 2012 unmatched payments: {stats[0]:,}")
    print(f"  Unique combinations: {stats[1]:,}")
    print(f"  Payments to KEEP: {stats[2]:,}")
    print(f"  Payments to DELETE: {stats[3]:,}")
    print(f"  Amount to delete: ${float(stats[4]):,.2f}")
    
    # Show samples
    print("\n" + "=" * 100)
    print("SAMPLE DUPLICATES TO DELETE (showing first 20)")
    print("=" * 100)
    print(f"{'Payment ID':<12} {'Date':<12} {'Amount':<12} {'Account':<15} {'Payment Key':<30}")
    print("-" * 100)
    
    for i, row in enumerate(to_delete[:20]):
        pid, date, amount, account, key = row
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
        account_str = (account[:12] if account else 'NULL')
        key_str = (key[:27] + '...' if key and len(key) > 27 else (key or 'NULL'))
        print(f"{pid:<12} {date_str:<12} {amount_str:<12} {account_str:<15} {key_str:<30}")
    
    if len(to_delete) > 20:
        print(f"... and {len(to_delete) - 20} more")
    
    # Show what we're keeping (sample pairs)
    print("\n" + "=" * 100)
    print("SAMPLE DUPLICATE PAIRS (Keep vs Delete)")
    print("=" * 100)
    
    cur.execute("""
        WITH duplicates AS (
            SELECT 
                payment_id,
                payment_date,
                amount,
                account_number,
                ROW_NUMBER() OVER (
                    PARTITION BY payment_date, amount, COALESCE(account_number, '')
                    ORDER BY payment_id
                ) as row_num
            FROM payments
            WHERE charter_id IS NULL
            AND EXTRACT(YEAR FROM payment_date) = 2012
            AND amount > 0
        )
        SELECT 
            payment_date,
            amount,
            account_number,
            MIN(CASE WHEN row_num = 1 THEN payment_id END) as keep_id,
            MAX(CASE WHEN row_num > 1 THEN payment_id END) as delete_id
        FROM duplicates
        GROUP BY payment_date, amount, account_number
        HAVING COUNT(*) > 1
        ORDER BY amount DESC
        LIMIT 10
    """)
    
    pairs = cur.fetchall()
    print(f"{'Date':<12} {'Amount':<12} {'Account':<15} {'KEEP ID':<12} {'DELETE ID':<12}")
    print("-" * 73)
    for date, amount, account, keep_id, delete_id in pairs:
        date_str = date.strftime('%Y-%m-%d') if date else 'NULL'
        amount_str = f"${float(amount):,.2f}" if amount else "$0.00"
        account_str = (account[:12] if account else 'NULL')
        print(f"{date_str:<12} {amount_str:<12} {account_str:<15} {keep_id:<12} {delete_id:<12}")
    
    # Apply deletions if --write flag
    if args.write:
        print("\n" + "=" * 100)
        print("APPLYING DELETIONS")
        print("=" * 100)
        
        # Create backup before deletion
        print("\n1. Creating backup...")
        backup_name = create_backup_before_delete(
            cur, 
            'payments',
            condition=f"payment_id IN ({','.join(str(row[0]) for row in to_delete)})"
        )
        print(f"✓ Backup created: {backup_name}")
        
        # Delete income_ledger entries first (to avoid foreign key constraint)
        print("\n2. Deleting income_ledger entries for duplicate payments...")
        delete_ids = [row[0] for row in to_delete]
        
        # Delete income_ledger in batches of 100
        income_deleted_total = 0
        for i in range(0, len(delete_ids), 100):
            batch = delete_ids[i:i+100]
            cur.execute(f"""
                DELETE FROM income_ledger
                WHERE payment_id IN ({','.join(str(pid) for pid in batch)})
            """)
            income_deleted_total += cur.rowcount
            if cur.rowcount > 0:
                print(f"   Deleted income_ledger batch {i//100 + 1}: {cur.rowcount} entries")
        
        print(f"✓ Deleted {income_deleted_total} income_ledger entries")
        
        # Now delete the duplicate payments
        print("\n3. Deleting duplicate payments...")
        
        # Delete in batches of 100 to avoid huge query
        deleted_total = 0
        for i in range(0, len(delete_ids), 100):
            batch = delete_ids[i:i+100]
            cur.execute(f"""
                DELETE FROM payments
                WHERE payment_id IN ({','.join(str(pid) for pid in batch)})
            """)
            deleted_total += cur.rowcount
            print(f"   Deleted batch {i//100 + 1}: {cur.rowcount} rows")
        
        # Log deletion
        log_deletion_audit(
            'payments',
            deleted_total,
            condition=f"2012 QBO duplicate payments (kept lower payment_id from each pair)"
        )
        
        conn.commit()
        
        print(f"\n✓ Successfully deleted {deleted_total} duplicate payments")
        print(f"✓ Backup: {backup_name}")
        print(f"✓ Audit log updated")
        
        # Verify final count
        cur.execute("""
            SELECT COUNT(*)
            FROM payments
            WHERE charter_id IS NULL
            AND EXTRACT(YEAR FROM payment_date) = 2012
            AND amount > 0
        """)
        remaining = cur.fetchone()[0]
        print(f"\n✓ Remaining 2012 unmatched payments: {remaining:,}")
        
    else:
        print("\n" + "=" * 100)
        print("DRY RUN COMPLETE - NO CHANGES APPLIED")
        print("=" * 100)
        print(f"\nTo apply these deletions, run:")
        print(f"  python remove_2012_duplicate_payments.py --write --override-key ALLOW_DELETE_PAYMENTS_20251108")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
