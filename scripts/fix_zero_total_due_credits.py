#!/usr/bin/env python3
"""
Fix charters with $0 total_amount_due but negative balances by setting paid_amount = 0 and balance = 0.
These are placeholder/cancelled charters where payments were incorrectly linked.

This will NOT delete the payment records, just set the charter's paid_amount to 0.
The payments will remain in the database but unlinked from these charters.
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
    parser = argparse.ArgumentParser(description='Fix charters with $0 total_due but negative balances')
    parser.add_argument('--write', action='store_true', help='Actually perform the fix (default: dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("FIXING CHARTERS WITH $0 TOTAL_DUE BUT NEGATIVE BALANCES")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    
    # Get charters to fix
    cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            charter_date,
            total_amount_due,
            paid_amount,
            balance
        FROM charters
        WHERE balance < 0
        AND COALESCE(total_amount_due, 0) = 0
        AND cancelled = FALSE
        ORDER BY balance ASC
    """)
    
    charters = cur.fetchall()
    
    print(f"\nFound {len(charters):,} charters to fix")
    
    if not charters:
        print("No charters to fix!")
        cur.close()
        conn.close()
        return
    
    # Show sample
    print(f"\n{'-'*80}")
    print("SAMPLE CHARTERS (first 10):")
    print(f"{'-'*80}")
    
    total_paid_to_clear = 0
    for charter in charters[:10]:
        charter_id, reserve, date, total_due, paid, balance = charter
        total_paid_to_clear += paid or 0
        total_due = total_due or 0
        paid = paid or 0
        balance = balance or 0
        date_str = str(date) if date else 'N/A'
        print(f"{reserve:<10} {date_str:<12} Total: ${total_due:>8,.2f} Paid: ${paid:>10,.2f} Balance: ${balance:>10,.2f}")
    
    if len(charters) > 10:
        print(f"... and {len(charters) - 10} more")
    
    total_paid_to_clear = sum(c[4] for c in charters)
    
    print(f"\n{'-'*80}")
    print("SUMMARY:")
    print(f"{'-'*80}")
    print(f"Charters to fix:                   {len(charters):,}")
    print(f"Total paid_amount to clear:        ${total_paid_to_clear:,.2f}")
    print(f"\nACTION: Set paid_amount = 0, balance = 0 for these charters")
    print(f"NOTE: Payment records will remain but be unlinked from these charters")
    
    if args.write:
        print(f"\n{'='*80}")
        print("CREATING BACKUP AND APPLYING FIX...")
        print(f"{'='*80}")
        
        # Create backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f'charters_zero_total_due_backup_{timestamp}'
        
        charter_ids = [str(c[0]) for c in charters]
        charter_ids_str = ','.join(charter_ids)
        
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM charters
            WHERE charter_id IN ({charter_ids_str})
        """)
        
        backup_count = cur.rowcount
        print(f"\n✓ Created backup: {backup_table}")
        print(f"  Backed up {backup_count:,} charter records")
        
        # Update charters
        cur.execute(f"""
            UPDATE charters
            SET paid_amount = 0,
                balance = 0
            WHERE charter_id IN ({charter_ids_str})
        """)
        
        updated_count = cur.rowcount
        print(f"✓ Updated {updated_count:,} charters")
        
        conn.commit()
        
        # Verify
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE balance < 0
            AND COALESCE(total_amount_due, 0) = 0
            AND cancelled = FALSE
        """)
        
        remaining = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE balance < 0
            AND cancelled = FALSE
        """)
        
        total_remaining = cur.fetchone()[0]
        
        print(f"\n{'='*80}")
        print("COMPLETION:")
        print(f"{'='*80}")
        print(f"✓ Fixed {updated_count:,} charters")
        print(f"✓ Cleared ${total_paid_to_clear:,.2f} in paid_amount")
        print(f"✓ Remaining with $0 total_due and negative balance: {remaining:,}")
        print(f"✓ Total remaining negative balances: {total_remaining:,}")
        
    else:
        print(f"\n[WARN]  DRY-RUN MODE - No changes made")
        print(f"   Run with --write to apply fix")
    
    print(f"\n{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
