"""
Remove duplicate payment records.
Keeps the oldest payment_id, removes duplicates with same (reserve_number, payment_date, amount).
"""

import psycopg2
import os
import argparse
from datetime import datetime
from table_protection import create_backup_before_delete, log_deletion_audit

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Remove duplicate payment records')
    parser.add_argument('--write', action='store_true', help='Actually delete duplicates')
    parser.add_argument('--limit', type=int, help='Limit number of duplicates to remove')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("REMOVE DUPLICATE PAYMENT RECORDS")
        print("=" * 80)
        
        # Find duplicates: same reserve_number, payment_date, amount
        cur.execute("""
            SELECT 
                reserve_number,
                payment_date,
                amount,
                COUNT(*) as dup_count,
                ARRAY_AGG(payment_id ORDER BY payment_id) as payment_ids
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number, payment_date, amount
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC, amount DESC
        """)
        
        raw_duplicates = cur.fetchall()
        
        if not raw_duplicates:
            print("\n✓ No duplicate payments found")
            return
        
        # Process to extract keep/delete IDs
        duplicates = []
        for reserve, pay_date, amount, dup_count, payment_ids in raw_duplicates:
            keep_id = payment_ids[0]
            delete_ids = payment_ids[1:]
            duplicates.append((reserve, pay_date, amount, dup_count, keep_id, delete_ids))
        
        print(f"\n[WARN]  Found {len(duplicates)} sets of duplicate payments")
        
        # Calculate totals
        total_dup_payments = sum(len(d[5]) for d in duplicates)
        total_dup_amount = sum(d[2] * len(d[5]) for d in duplicates)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Duplicate sets: {len(duplicates)}")
        print(f"   Duplicate payment records to delete: {total_dup_payments:,}")
        print(f"   Duplicate amount: ${total_dup_amount:,.2f}")
        
        # Show samples
        print(f"\n📋 TOP 20 DUPLICATE SETS:")
        print(f"\n{'Reserve':<10} {'Date':<12} {'Amount':>12} {'Count':>6} Keep ID   Delete IDs")
        print("-" * 90)
        
        for i, (reserve, pay_date, amount, count, keep_id, delete_ids) in enumerate(duplicates[:20]):
            delete_ids_str = str(delete_ids[:3])[1:-1]
            if len(delete_ids) > 3:
                delete_ids_str += f"... +{len(delete_ids)-3} more"
            print(f"{reserve:<10} {str(pay_date):<12} ${amount:>10,.2f} {count:>6}x {keep_id:<9} [{delete_ids_str}]")
        
        if args.write:
            # Collect all payment_ids to delete
            all_delete_ids = []
            for dup in duplicates:
                all_delete_ids.extend(dup[5])
            
            if args.limit:
                all_delete_ids = all_delete_ids[:args.limit]
                print(f"\n[WARN]  Limiting to {args.limit} deletions")
            
            print(f"\n📦 Creating backup...")
            backup_name = create_backup_before_delete(
                cur,
                'payments',
                condition=f"payment_id IN ({','.join(map(str, all_delete_ids))})"
            )
            print(f"   ✓ Backup: {backup_name}")
            
            # Delete foreign key references first
            print(f"\n🗑️  Deleting foreign key references...")
            
            # Income ledger
            cur.execute(f"""
                DELETE FROM income_ledger
                WHERE payment_id IN ({','.join(map(str, all_delete_ids))})
            """)
            ledger_deleted = cur.rowcount
            print(f"   ✓ Deleted {ledger_deleted:,} income_ledger entries")
            
            # Banking payment links
            cur.execute(f"""
                DELETE FROM banking_payment_links
                WHERE payment_id IN ({','.join(map(str, all_delete_ids))})
            """)
            banking_deleted = cur.rowcount
            print(f"   ✓ Deleted {banking_deleted:,} banking_payment_links entries")
            
            # Delete duplicates
            print(f"\n🗑️  Deleting {len(all_delete_ids):,} duplicate payments...")
            cur.execute(f"""
                DELETE FROM payments
                WHERE payment_id IN ({','.join(map(str, all_delete_ids))})
            """)
            deleted_count = cur.rowcount
            
            log_deletion_audit('payments', deleted_count, 
                             condition=f"payment_id IN (duplicate list - {len(all_delete_ids)} ids)")
            
            conn.commit()
            
            print(f"   ✓ Deleted {deleted_count:,} duplicate payments")
            
            # Verify
            cur.execute("""
                SELECT COUNT(*), SUM(amount)
                FROM payments
            """)
            remaining_count, remaining_sum = cur.fetchone()
            print(f"\n📊 REMAINING PAYMENTS:")
            print(f"   Count: {remaining_count:,}")
            print(f"   Total: ${remaining_sum or 0:,.2f}")
            
        else:
            print("\n" + "=" * 80)
            print("DRY RUN MODE")
            print("=" * 80)
            print(f"\nWould delete {total_dup_payments:,} duplicate payment records")
            print("\nTo remove duplicates, run with: --write")
            if total_dup_payments > 1000:
                print("Consider using --limit to process in batches")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
