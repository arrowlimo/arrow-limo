"""
Force recalculation of ALL charter paid_amount and balance from payments.
Uses reserve_number to sum payments (not charter_id).
No comparison check - just recalculates everything.
"""

import psycopg2
import os
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Force recalculate all charter amounts')
    parser.add_argument('--write', action='store_true', help='Actually update the database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("FORCE RECALCULATE ALL CHARTER PAID_AMOUNT FROM PAYMENTS")
        print("=" * 80)
        
        # Get total charters
        cur.execute("SELECT COUNT(*) FROM charters")
        total_charters = cur.fetchone()[0]
        
        print(f"\n📊 Total charters: {total_charters:,}")
        
        if args.write:
            # Create backup
            backup_table = f"charters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"\n📦 Creating backup: {backup_table}...")
            cur.execute(f"""
                CREATE TABLE {backup_table} AS 
                SELECT * FROM charters
            """)
            backup_count = cur.rowcount
            print(f"   ✓ Backed up {backup_count:,} charters")
            
            # Recalculate paid_amount and balance for ALL charters
            print(f"\n🔄 Recalculating paid_amount and balance...")
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
                  AND (c.paid_amount IS DISTINCT FROM ps.actual_paid 
                       OR c.balance IS DISTINCT FROM (c.total_amount_due - ps.actual_paid))
            """)
            updated_count = cur.rowcount
            
            # Also update charters with no payments to paid_amount=0
            cur.execute("""
                UPDATE charters c
                SET paid_amount = 0,
                    balance = c.total_amount_due
                WHERE NOT EXISTS (
                    SELECT 1 FROM payments p 
                    WHERE p.reserve_number = c.reserve_number
                )
                AND (c.paid_amount != 0 OR c.balance != c.total_amount_due)
            """)
            zero_payment_count = cur.rowcount
            
            conn.commit()
            
            print(f"   ✓ Updated {updated_count:,} charters with payments")
            print(f"   ✓ Updated {zero_payment_count:,} charters with no payments")
            print(f"   ✓ Total updated: {updated_count + zero_payment_count:,}")
            
            # Verify
            cur.execute("""
                SELECT COUNT(*), SUM(balance)
                FROM charters
                WHERE balance < 0
            """)
            neg_count, neg_sum = cur.fetchone()
            
            cur.execute("""
                SELECT COUNT(*), SUM(balance)
                FROM charters
                WHERE balance > 0
            """)
            pos_count, pos_sum = cur.fetchone()
            
            print(f"\n📊 AFTER RECALCULATION:")
            print(f"   Negative balances (credits): {neg_count:,} charters, ${neg_sum or 0:,.2f}")
            print(f"   Positive balances (owing): {pos_count:,} charters, ${pos_sum or 0:,.2f}")
            
        else:
            print("\n" + "=" * 80)
            print("DRY RUN MODE")
            print("=" * 80)
            print("\nTo recalculate all charter amounts, run with: --write")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
