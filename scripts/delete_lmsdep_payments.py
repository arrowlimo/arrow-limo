#!/usr/bin/env python3
"""
Delete all LMSDEP batch payments and restart LMS payment matching.
These were incorrectly attributed deposits causing massive false credits.
"""

import psycopg2
import os
import argparse
from datetime import datetime
from table_protection import create_backup_before_delete, log_deletion_audit, protect_deletion

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(
        description='Delete all LMSDEP batch payments (misattributed deposits)'
    )
    parser.add_argument('--write', action='store_true',
                       help='Actually delete payments (default is dry-run)')
    parser.add_argument('--override-key', type=str,
                       help='Override key for deletion protection')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("DELETE LMSDEP BATCH PAYMENTS")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    # Find all LMSDEP payments
    print("Finding LMSDEP batch payments...")
    cur.execute("""
        SELECT 
            payment_id,
            reserve_number,
            payment_date,
            amount,
            payment_key
        FROM payments
        WHERE payment_key LIKE 'LMSDEP:%'
        ORDER BY payment_date, payment_id
    """)
    
    lmsdep_payments = cur.fetchall()
    
    if not lmsdep_payments:
        print("✓ No LMSDEP payments found")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(lmsdep_payments)} LMSDEP payments")
    print()
    
    # Summary by reserve
    from collections import defaultdict
    by_reserve = defaultdict(list)
    total_amount = 0
    
    for pmt in lmsdep_payments:
        pid, reserve, pdate, amount, pkey = pmt
        by_reserve[reserve].append((pid, amount, pdate, pkey))
        total_amount += amount
    
    print(f"Reserves affected: {len(by_reserve)}")
    print(f"Total amount to remove: ${total_amount:,.2f}")
    print()
    
    # Show top 20 affected reserves
    print("Top 20 most affected reserves:")
    print(f"{'Reserve':<10} {'Payments':<10} {'Total Amount':<15}")
    print("-" * 40)
    
    sorted_reserves = sorted(by_reserve.items(), 
                            key=lambda x: sum(p[1] for p in x[1]), 
                            reverse=True)
    
    for reserve, pmts in sorted_reserves[:20]:
        total = sum(p[1] for p in pmts)
        reserve_str = reserve if reserve else "NULL"
        print(f"{reserve_str:<10} {len(pmts):<10} ${total:<14,.2f}")
    
    print()
    
    if args.write:
        # Check protection
        try:
            protect_deletion('payments', dry_run=False, override_key=args.override_key)
        except Exception as e:
            print(f"✗ Protection check failed: {e}")
            print(f"\nTo override, use: --override-key ALLOW_DELETE_PAYMENTS_{datetime.now().strftime('%Y%m%d')}")
            cur.close()
            conn.close()
            return
        
        print("=" * 80)
        print("DELETING LMSDEP PAYMENTS...")
        print("=" * 80)
        
        # Create backup
        backup_name = create_backup_before_delete(
            cur,
            'payments',
            condition="payment_key LIKE 'LMSDEP:%'"
        )
        print(f"✓ Created backup: {backup_name}")
        print()
        
        # Delete foreign key references first
        print("Deleting income_ledger references...")
        cur.execute("""
            DELETE FROM income_ledger 
            WHERE payment_id IN (
                SELECT payment_id FROM payments WHERE payment_key LIKE 'LMSDEP:%'
            )
        """)
        fk_deleted = cur.rowcount
        print(f"✓ Deleted {fk_deleted} income_ledger references")
        
        # Delete banking_payment_links references
        print("Deleting banking_payment_links references...")
        cur.execute("""
            DELETE FROM banking_payment_links 
            WHERE payment_id IN (
                SELECT payment_id FROM payments WHERE payment_key LIKE 'LMSDEP:%'
            )
        """)
        bpl_deleted = cur.rowcount
        print(f"✓ Deleted {bpl_deleted} banking_payment_links references")
        
        # Clear self-referencing related_payment_id to break cycle
        print("Clearing related_payment_id self-references...")
        cur.execute("""
            UPDATE payments 
            SET related_payment_id = NULL 
            WHERE related_payment_id IN (
                SELECT payment_id FROM payments WHERE payment_key LIKE 'LMSDEP:%'
            )
        """)
        related_cleared = cur.rowcount
        print(f"✓ Cleared {related_cleared} related_payment_id references")
        
        # Delete the payments
        print("\nDeleting LMSDEP payments...")
        cur.execute("DELETE FROM payments WHERE payment_key LIKE 'LMSDEP:%'")
        deleted = cur.rowcount
        print(f"✓ Deleted {deleted} payments")
        
        # Update charter balances
        print("\nRecalculating charter balances...")
        
        affected_reserves = list(by_reserve.keys())
        for reserve in affected_reserves:
            # Recalculate paid_amount from remaining payments
            cur.execute("""
                UPDATE charters 
                SET paid_amount = COALESCE((
                    SELECT SUM(amount) 
                    FROM payments 
                    WHERE reserve_number = %s
                ), 0),
                balance = total_amount_due - COALESCE((
                    SELECT SUM(amount) 
                    FROM payments 
                    WHERE reserve_number = %s
                ), 0),
                updated_at = %s
                WHERE reserve_number = %s
            """, (reserve, reserve, datetime.now(), reserve))
        
        print(f"✓ Updated {len(affected_reserves)} charters")
        
        # Log the deletion
        log_deletion_audit('payments', deleted, 
                          condition=f"payment_key LIKE 'LMSDEP:%' - {len(affected_reserves)} reserves affected")
        
        conn.commit()
        
        print()
        print("=" * 80)
        print("✓ DELETION COMPLETE")
        print("=" * 80)
        print(f"Deleted: {deleted} payments")
        print(f"Removed amount: ${total_amount:,.2f}")
        print(f"Charters updated: {len(affected_reserves)}")
        
    else:
        print("=" * 80)
        print("DRY-RUN COMPLETE")
        print("=" * 80)
        print(f"\nTo delete these payments, run with:")
        print(f"  --write --override-key ALLOW_DELETE_PAYMENTS_{datetime.now().strftime('%Y%m%d')}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
