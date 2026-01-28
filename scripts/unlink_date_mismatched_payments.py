"""
Unlink payments that are >1 year date mismatch from their charter.
These were incorrectly auto-matched by amount patterns.
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
    parser = argparse.ArgumentParser(description='Unlink date-mismatched payments')
    parser.add_argument('--write', action='store_true', help='Actually unlink payments')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("UNLINK DATE-MISMATCHED AUTO-MATCHED PAYMENTS")
        print("=" * 80)
        
        # Find mismatched payments
        cur.execute("""
            SELECT 
                p.payment_id,
                p.reserve_number,
                c.charter_date,
                p.payment_date,
                p.amount,
                ABS(p.payment_date - c.charter_date) as days_diff
            FROM payments p
            JOIN charters c ON c.reserve_number = p.reserve_number
            WHERE p.payment_date IS NOT NULL
              AND c.charter_date IS NOT NULL
              AND ABS(p.payment_date - c.charter_date) > 365
              AND p.notes LIKE '%AUTO-MATCHED%'
            ORDER BY p.payment_id
        """)
        
        mismatched = cur.fetchall()
        
        if not mismatched:
            print("\n✓ No date-mismatched payments found")
            return
        
        print(f"\n[WARN]  Found {len(mismatched)} payments with >1 year mismatch")
        
        total_amount = sum(m[4] for m in mismatched)
        print(f"   Total amount: ${total_amount:,.2f}")
        
        # Show sample
        print(f"\n📋 SAMPLE (first 10):")
        print(f"\n{'Payment ID':<12} {'Reserve':<10} {'Charter':<12} {'Payment':<12} {'Amount':>12} {'Days Off':>10}")
        print("-" * 80)
        
        for i, (pid, reserve, charter_date, payment_date, amount, days_diff) in enumerate(mismatched[:10]):
            print(f"{pid:<12} {reserve:<10} {str(charter_date):<12} {str(payment_date):<12} ${amount:>10,.2f} {days_diff:>9}d")
        
        if args.write:
            payment_ids = [m[0] for m in mismatched]
            
            # Create backup
            print(f"\n📦 Creating backup...")
            backup_name = create_backup_before_delete(
                cur,
                'payments',
                condition=f"payment_id IN ({','.join(map(str, payment_ids))})"
            )
            print(f"   ✓ Backup: {backup_name}")
            
            # Unlink by setting reserve_number = NULL
            print(f"\n🔗 Unlinking {len(payment_ids)} payments...")
            cur.execute(f"""
                UPDATE payments
                SET reserve_number = NULL,
                    charter_id = NULL,
                    notes = COALESCE(notes || E'\n', '') || 
                            '[{datetime.now().strftime('%Y-%m-%d')}] Unlinked: Date mismatch >1 year from charter'
                WHERE payment_id IN ({','.join(map(str, payment_ids))})
            """)
            unlinked_count = cur.rowcount
            
            log_deletion_audit('payments', unlinked_count, 
                             condition=f"Unlinked {len(payment_ids)} date-mismatched payments")
            
            conn.commit()
            
            print(f"   ✓ Unlinked {unlinked_count} payments")
            
            # Recalculate affected charters
            affected_reserves = list(set(m[1] for m in mismatched))
            print(f"\n🔄 Recalculating {len(affected_reserves)} affected charters...")
            
            cur.execute(f"""
                WITH payment_sums AS (
                    SELECT 
                        reserve_number,
                        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                    FROM payments
                    WHERE reserve_number IN ({','.join(f"'{r}'" for r in affected_reserves)})
                    GROUP BY reserve_number
                )
                UPDATE charters c
                SET paid_amount = COALESCE(ps.actual_paid, 0),
                    balance = c.total_amount_due - COALESCE(ps.actual_paid, 0)
                FROM payment_sums ps
                WHERE c.reserve_number = ps.reserve_number
            """)
            recalc_count = cur.rowcount
            
            conn.commit()
            
            print(f"   ✓ Recalculated {recalc_count} charters")
            
            # Verify
            cur.execute("""
                SELECT COUNT(*), SUM(ABS(balance))
                FROM charters
                WHERE balance < 0
            """)
            neg_count, neg_sum = cur.fetchone()
            
            print(f"\n📊 REMAINING NEGATIVE BALANCES:")
            print(f"   Count: {neg_count}")
            print(f"   Total credits: ${neg_sum or 0:,.2f}")
            
        else:
            print("\n" + "=" * 80)
            print("DRY RUN MODE")
            print("=" * 80)
            print(f"\nWould unlink {len(mismatched)} payments (${total_amount:,.2f})")
            print("\nTo unlink payments, run with: --write")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
