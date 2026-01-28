#!/usr/bin/env python3
"""
Remove ALL types of duplicate payments, keeping only one per (charter_id, amount, date) group.

Priority for which to keep:
1. LMS Import (most recent import, most reliable)
2. Square (if no LMS import)
3. AUTO-MATCHED (if no LMS or Square)
4. Auto-linked (lowest priority)

For duplicates, keep the HIGHEST payment_id (most recent).
"""

import psycopg2
import argparse
from datetime import datetime

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Remove all duplicate payments')
    parser.add_argument('--write', action='store_true', help='Actually delete duplicates (default: dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number to process (for testing)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("REMOVING ALL DUPLICATE PAYMENTS")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    if args.limit:
        print(f"Limit: {args.limit}")
    
    # Find all duplicate payment groups (same charter, amount, date)
    cur.execute("""
        WITH payment_groups AS (
            SELECT 
                charter_id,
                amount,
                payment_date,
                COUNT(*) as dup_count,
                ARRAY_AGG(payment_id ORDER BY payment_id DESC) as payment_ids,
                ARRAY_AGG(notes ORDER BY payment_id DESC) as notes_list
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY charter_id, amount, payment_date
            HAVING COUNT(*) > 1
        )
        SELECT 
            charter_id,
            amount,
            payment_date,
            dup_count,
            payment_ids,
            notes_list
        FROM payment_groups
        ORDER BY dup_count DESC, amount DESC
    """)
    
    duplicate_groups = cur.fetchall()
    
    print(f"\nFound {len(duplicate_groups):,} groups with duplicate payments")
    
    if not duplicate_groups:
        print("No duplicates found!")
        cur.close()
        conn.close()
        return
    
    # Process each group and determine which to keep
    payments_to_delete = []
    payments_to_keep = []
    
    print(f"\n{'-'*80}")
    print("ANALYZING DUPLICATES (first 20 groups):")
    print(f"{'-'*80}")
    
    for i, group in enumerate(duplicate_groups[:20]):
        charter_id, amount, date, dup_count, payment_ids, notes_list = group
        
        print(f"\n{i+1}. Charter {charter_id}, ${amount:,.2f} on {date}")
        print(f"   {dup_count} duplicate payments: {payment_ids}")
        
        # Determine which to keep based on priority
        keep_id = None
        delete_ids = []
        
        # Priority 1: LMS Import (highest payment_id with this note type)
        for j, note in enumerate(notes_list):
            if note and 'Imported from LMS Payment ID' in note:
                keep_id = payment_ids[j]
                print(f"   → KEEP {keep_id} (LMS Import)")
                break
        
        # Priority 2: Square (if no LMS import)
        if not keep_id:
            for j, note in enumerate(notes_list):
                if note and '[Square]' in note:
                    keep_id = payment_ids[j]
                    print(f"   → KEEP {keep_id} (Square)")
                    break
        
        # Priority 3: Highest payment_id (most recent)
        if not keep_id:
            keep_id = payment_ids[0]  # Already sorted DESC
            print(f"   → KEEP {keep_id} (Most recent)")
        
        # All others are marked for deletion
        for pid in payment_ids:
            if pid != keep_id:
                delete_ids.append(pid)
                payments_to_delete.append(pid)
        
        payments_to_keep.append(keep_id)
        
        if delete_ids:
            print(f"   → DELETE {delete_ids}")
    
    if len(duplicate_groups) > 20:
        print(f"\n... and {len(duplicate_groups) - 20} more groups")
        
        # Process remaining groups silently
        for group in duplicate_groups[20:]:
            charter_id, amount, date, dup_count, payment_ids, notes_list = group
            
            keep_id = None
            
            # Same priority logic
            for j, note in enumerate(notes_list):
                if note and 'Imported from LMS Payment ID' in note:
                    keep_id = payment_ids[j]
                    break
            
            if not keep_id:
                for j, note in enumerate(notes_list):
                    if note and '[Square]' in note:
                        keep_id = payment_ids[j]
                        break
            
            if not keep_id:
                keep_id = payment_ids[0]
            
            for pid in payment_ids:
                if pid != keep_id:
                    payments_to_delete.append(pid)
            
            payments_to_keep.append(keep_id)
    
    # Calculate impact
    cur.execute(f"""
        SELECT 
            COUNT(*),
            SUM(amount)
        FROM payments
        WHERE payment_id = ANY(%s)
    """, (payments_to_delete,))
    
    delete_count, delete_amount = cur.fetchone()
    
    affected_charters = set()
    for group in duplicate_groups:
        affected_charters.add(group[0])
    
    print(f"\n{'-'*80}")
    print("SUMMARY:")
    print(f"{'-'*80}")
    print(f"Duplicate groups:                  {len(duplicate_groups):,}")
    print(f"Payments to DELETE:                {delete_count:,}")
    print(f"Payments to KEEP:                  {len(payments_to_keep):,}")
    print(f"Amount to remove (duplicates):     ${delete_amount:,.2f}")
    print(f"Affected charters:                 {len(affected_charters):,}")
    
    # Apply changes
    if args.write and payments_to_delete:
        print(f"\n{'='*80}")
        print("CREATING BACKUP AND DELETING DUPLICATES...")
        print(f"{'='*80}")
        
        # Create backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f'payments_all_duplicates_backup_{timestamp}'
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM payments
            WHERE payment_id = ANY(%s)
        """, (payments_to_delete,))
        
        backup_count = cur.rowcount
        print(f"\n✓ Created backup: {backup_table}")
        print(f"  Backed up {backup_count:,} payments")
        
        # Delete foreign key references
        cur.execute("""
            DELETE FROM income_ledger
            WHERE payment_id = ANY(%s)
        """, (payments_to_delete,))
        
        income_deleted = cur.rowcount
        print(f"✓ Deleted {income_deleted:,} income_ledger entries")
        
        cur.execute("""
            DELETE FROM banking_payment_links
            WHERE payment_id = ANY(%s)
        """, (payments_to_delete,))
        
        banking_deleted = cur.rowcount
        print(f"✓ Deleted {banking_deleted:,} banking_payment_links entries")
        
        # Delete the payments
        cur.execute("""
            DELETE FROM payments
            WHERE payment_id = ANY(%s)
        """, (payments_to_delete,))
        
        payments_deleted = cur.rowcount
        print(f"✓ Deleted {payments_deleted:,} duplicate payments")
        
        # Recalculate balances
        print(f"\nRecalculating balances for {len(affected_charters):,} affected charters...")
        
        affected_charters_list = list(affected_charters)
        
        cur.execute("""
            WITH payment_sums AS (
                SELECT 
                    charter_id,
                    COALESCE(SUM(amount), 0) as total_paid
                FROM payments
                WHERE charter_id = ANY(%s)
                GROUP BY charter_id
            )
            UPDATE charters
            SET paid_amount = COALESCE(ps.total_paid, 0),
                balance = COALESCE(total_amount_due, 0) - COALESCE(ps.total_paid, 0)
            FROM payment_sums ps
            WHERE charters.charter_id = ps.charter_id
        """, (affected_charters_list,))
        
        recalc_count = cur.rowcount
        print(f"✓ Recalculated {recalc_count:,} charter balances")
        
        # Update charters with no payments
        cur.execute("""
            UPDATE charters
            SET paid_amount = 0,
                balance = COALESCE(total_amount_due, 0)
            WHERE charter_id = ANY(%s)
            AND charter_id NOT IN (SELECT DISTINCT charter_id FROM payments WHERE reserve_number IS NOT NULL)
        """, (affected_charters_list,))
        
        zero_count = cur.rowcount
        if zero_count > 0:
            print(f"✓ Reset {zero_count:,} charters with no payments")
        
        conn.commit()
        
        # Final stats
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE balance < 0
            AND cancelled = FALSE
        """)
        
        remaining_credits = cur.fetchone()[0]
        
        print(f"\n{'='*80}")
        print("COMPLETION:")
        print(f"{'='*80}")
        print(f"✓ Deleted {payments_deleted:,} duplicate payments")
        print(f"✓ Removed ${delete_amount:,.2f} in duplicates")
        print(f"✓ Updated {recalc_count:,} charter balances")
        print(f"✓ Remaining negative balances: {remaining_credits:,}")
        
    else:
        print(f"\n[WARN]  DRY-RUN MODE - No changes made")
        print(f"   Run with --write to delete duplicates")
    
    print(f"\n{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
