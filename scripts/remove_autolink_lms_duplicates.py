#!/usr/bin/env python3
"""
Remove duplicate payments where:
1. Same reserve_number, amount, and payment_date
2. One is "Auto-linked" and one is "Imported from LMS Payment ID X"
3. AND the LMS Payment ID matches

Keep the LMS imported one (newer, more reliable), delete the auto-linked one.
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
    parser = argparse.ArgumentParser(description='Remove duplicate auto-linked/LMS import payments')
    parser.add_argument('--write', action='store_true', help='Actually delete the duplicates (default: dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number of duplicates to process')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("REMOVING DUPLICATE AUTO-LINKED / LMS IMPORT PAYMENTS")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    if args.limit:
        print(f"Limit: {args.limit} duplicates")
    
    # Find auto-linked/LMS import duplicate pairs
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""
    
    cur.execute(f"""
        WITH auto_linked AS (
            SELECT 
                payment_id, 
                charter_id,
                reserve_number, 
                amount, 
                payment_date, 
                notes,
                created_at
            FROM payments
            WHERE notes LIKE '%Auto-linked%'
        ),
        lms_imported AS (
            SELECT 
                payment_id, 
                charter_id,
                reserve_number, 
                amount, 
                payment_date, 
                notes,
                created_at
            FROM payments
            WHERE notes LIKE '%Imported from LMS Payment ID%'
        )
        SELECT 
            a.payment_id as auto_id,
            a.charter_id as auto_charter_id,
            l.payment_id as lms_id,
            l.charter_id as lms_charter_id,
            a.reserve_number,
            a.amount,
            a.payment_date,
            a.notes as auto_notes,
            l.notes as lms_notes
        FROM auto_linked a
        JOIN lms_imported l ON 
            a.reserve_number = l.reserve_number
            AND a.amount = l.amount
            AND a.payment_date = l.payment_date
        WHERE a.payment_id != l.payment_id
        ORDER BY a.amount DESC
        {limit_clause}
    """)
    
    duplicates = cur.fetchall()
    
    print(f"\nFound {len(duplicates):,} auto-linked/LMS import duplicate pairs")
    
    if not duplicates:
        print("No duplicates to remove!")
        cur.close()
        conn.close()
        return
    
    # Show sample
    print(f"\n{'-'*80}")
    print("SAMPLE DUPLICATES (first 10):")
    print(f"{'-'*80}")
    
    for i, dup in enumerate(duplicates[:10]):
        auto_id, auto_cid, lms_id, lms_cid, reserve, amount, date, auto_notes, lms_notes = dup
        print(f"\n{i+1}. Reserve {reserve}, ${amount:,.2f} on {date}")
        print(f"   Auto-linked payment ID: {auto_id} (charter {auto_cid}) - TO DELETE")
        print(f"   LMS import payment ID: {lms_id} (charter {lms_cid}) - TO KEEP")
        
        # Extract LMS payment ID from import notes
        if 'Imported from LMS Payment ID' in lms_notes:
            lms_payment_id = lms_notes.split('Imported from LMS Payment ID ')[1].split()[0]
            print(f"   LMS Payment ID: {lms_payment_id}")
    
    if len(duplicates) > 10:
        print(f"\n... and {len(duplicates) - 10} more")
    
    # Calculate impact
    total_amount = sum(d[5] for d in duplicates)
    affected_charters = set()
    for d in duplicates:
        affected_charters.add(d[1])  # auto_charter_id
        affected_charters.add(d[3])  # lms_charter_id
    
    print(f"\n{'-'*80}")
    print(f"IMPACT SUMMARY:")
    print(f"{'-'*80}")
    print(f"Duplicate payments to delete:      {len(duplicates):,}")
    print(f"Total amount (will be removed once): ${total_amount:,.2f}")
    print(f"Affected charters:                 {len(affected_charters):,}")
    
    # Perform deletion
    if args.write:
        print(f"\n{'='*80}")
        print("CREATING BACKUP AND DELETING DUPLICATES...")
        print(f"{'='*80}")
        
        # Create backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f'payments_autolink_lms_dup_backup_{timestamp}'
        
        auto_ids = [str(d[0]) for d in duplicates]
        auto_ids_str = ','.join(auto_ids)
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM payments
            WHERE payment_id IN ({auto_ids_str})
        """)
        
        backup_count = cur.rowcount
        print(f"\n✓ Created backup table: {backup_table}")
        print(f"  Backed up {backup_count:,} payment records")
        
        # Delete from income_ledger first (foreign key)
        cur.execute(f"""
            DELETE FROM income_ledger
            WHERE payment_id IN ({auto_ids_str})
        """)
        
        income_deleted = cur.rowcount
        print(f"✓ Deleted {income_deleted:,} income_ledger entries")
        
        # Delete from banking_payment_links (foreign key)
        cur.execute(f"""
            DELETE FROM banking_payment_links
            WHERE payment_id IN ({auto_ids_str})
        """)
        
        banking_deleted = cur.rowcount
        print(f"✓ Deleted {banking_deleted:,} banking_payment_links entries")
        
        # Delete the duplicate payments
        cur.execute(f"""
            DELETE FROM payments
            WHERE payment_id IN ({auto_ids_str})
        """)
        
        payments_deleted = cur.rowcount
        print(f"✓ Deleted {payments_deleted:,} duplicate payment records")
        
        # Recalculate paid_amount and balance for affected charters
        print(f"\nRecalculating balances for {len(affected_charters):,} affected charters...")
        
        affected_charters_str = ','.join(str(c) for c in affected_charters)
        
        cur.execute(f"""
            WITH payment_sums AS (
                SELECT 
                    charter_id,
                    COALESCE(SUM(amount), 0) as total_paid
                FROM payments
                WHERE charter_id IN ({affected_charters_str})
                GROUP BY charter_id
            )
            UPDATE charters
            SET paid_amount = COALESCE(ps.total_paid, 0),
                balance = COALESCE(total_amount_due, 0) - COALESCE(ps.total_paid, 0)
            FROM payment_sums ps
            WHERE charters.charter_id = ps.charter_id
        """)
        
        recalc_count = cur.rowcount
        print(f"✓ Recalculated {recalc_count:,} charter balances")
        
        # Also update charters that now have no payments
        cur.execute(f"""
            UPDATE charters
            SET paid_amount = 0,
                balance = COALESCE(total_amount_due, 0)
            WHERE charter_id IN ({affected_charters_str})
            AND charter_id NOT IN (SELECT DISTINCT charter_id FROM payments WHERE reserve_number IS NOT NULL)
        """)
        
        zero_payment_count = cur.rowcount
        if zero_payment_count > 0:
            print(f"✓ Reset {zero_payment_count:,} charters with no remaining payments")
        
        conn.commit()
        
        # Verify results
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE balance < 0
            AND cancelled = FALSE
        """)
        
        remaining_credits = cur.fetchone()[0]
        
        print(f"\n{'='*80}")
        print(f"COMPLETION SUMMARY:")
        print(f"{'='*80}")
        print(f"✓ Deleted {payments_deleted:,} duplicate payments")
        print(f"✓ Removed ${total_amount:,.2f} in duplicate payment amounts")
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
