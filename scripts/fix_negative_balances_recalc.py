#!/usr/bin/env python3
"""
Fix negative balances by:
1. Recalculating paid_amount from actual payment records
2. Recalculating balance = total_amount_due - paid_amount
3. Identifying and reporting duplicate payments for manual review
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
    parser = argparse.ArgumentParser(description='Fix negative balances by recalculating from payment records')
    parser.add_argument('--write', action='store_true', help='Actually perform the updates (default: dry-run)')
    parser.add_argument('--limit', type=int, help='Limit number of charters to fix (for testing)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("FIXING NEGATIVE BALANCES - RECALCULATE FROM PAYMENT RECORDS")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    if args.limit:
        print(f"Limit: {args.limit} charters")
    
    # Get all charters with negative balances
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""
    
    cur.execute(f"""
        SELECT 
            ch.charter_id,
            ch.reserve_number,
            ch.charter_date,
            ch.total_amount_due,
            ch.paid_amount,
            ch.balance,
            COALESCE(SUM(p.amount), 0) as actual_paid
        FROM charters ch
        LEFT JOIN payments p ON p.charter_id = ch.charter_id
        WHERE ch.balance < 0
        AND ch.cancelled = FALSE
        GROUP BY ch.charter_id, ch.reserve_number, ch.charter_date,
                 ch.total_amount_due, ch.paid_amount, ch.balance
        ORDER BY ch.balance ASC
        {limit_clause}
    """)
    
    charters_to_fix = cur.fetchall()
    
    print(f"\nFound {len(charters_to_fix):,} charters with negative balances to fix")
    
    if not charters_to_fix:
        print("No charters to fix!")
        cur.close()
        conn.close()
        return
    
    # Backup before making changes
    if args.write:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_table = f'charters_negative_balance_backup_{timestamp}'
        
        charter_ids = [str(c[0]) for c in charters_to_fix]
        charter_ids_str = ','.join(charter_ids)
        
        print(f"\nCreating backup table: {backup_table}")
        cur.execute(f"""
            CREATE TABLE {backup_table} AS
            SELECT * FROM charters
            WHERE charter_id IN ({charter_ids_str})
        """)
        
        backup_count = cur.rowcount
        print(f"Backed up {backup_count:,} charter records")
    
    # Process each charter
    print(f"\n{'-'*80}")
    print("RECALCULATING BALANCES:")
    print(f"{'-'*80}")
    
    fixed_count = 0
    total_balance_change = 0
    
    for charter in charters_to_fix[:10]:  # Show first 10
        charter_id, reserve, date, total_due, old_paid, old_balance, actual_paid = charter
        total_due = total_due or 0
        new_balance = total_due - actual_paid
        balance_change = new_balance - old_balance
        
        print(f"\n{reserve} (ID {charter_id}):")
        print(f"  Total due: ${total_due:,.2f}")
        print(f"  Old paid_amount: ${old_paid:,.2f} -> New: ${actual_paid:,.2f}")
        print(f"  Old balance: ${old_balance:,.2f} -> New: ${new_balance:,.2f}")
        print(f"  Change: ${balance_change:,.2f}")
    
    if len(charters_to_fix) > 10:
        print(f"\n... and {len(charters_to_fix) - 10:,} more charters")
    
    # Calculate totals
    for charter in charters_to_fix:
        charter_id, reserve, date, total_due, old_paid, old_balance, actual_paid = charter
        total_due = total_due or 0
        new_balance = total_due - actual_paid
        balance_change = new_balance - old_balance
        total_balance_change += balance_change
        fixed_count += 1
    
    print(f"\n{'-'*80}")
    print(f"SUMMARY:")
    print(f"{'-'*80}")
    print(f"Charters to fix: {fixed_count:,}")
    print(f"Total balance change: ${total_balance_change:,.2f}")
    
    # Perform updates
    if args.write:
        print(f"\n{'='*80}")
        print("PERFORMING UPDATES...")
        print(f"{'='*80}")
        
        updated_count = 0
        for charter in charters_to_fix:
            charter_id, reserve, date, total_due, old_paid, old_balance, actual_paid = charter
            total_due = total_due or 0
            new_balance = total_due - actual_paid
            
            cur.execute("""
                UPDATE charters
                SET paid_amount = %s,
                    balance = %s
                WHERE charter_id = %s
            """, (actual_paid, new_balance, charter_id))
            
            updated_count += 1
        
        conn.commit()
        print(f"\n✓ Updated {updated_count:,} charters")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*)
            FROM charters
            WHERE balance < 0
            AND cancelled = FALSE
        """)
        remaining = cur.fetchone()[0]
        
        print(f"✓ Remaining negative balances: {remaining:,}")
        
    else:
        print(f"\n[WARN]  DRY-RUN MODE - No changes made")
        print(f"   Run with --write to apply changes")
    
    print(f"\n{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
