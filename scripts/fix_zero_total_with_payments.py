"""
Fix charters with $0 total_amount_due but have payments.
Set total_amount_due = paid_amount (the payments received represent the actual service value).
"""

import psycopg2
import os
import argparse
from datetime import datetime
from table_protection import create_backup_before_delete

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Fix charters with $0 total but payments received')
    parser.add_argument('--write', action='store_true', help='Actually update the database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("=" * 80)
        print("FIX CHARTERS WITH $0 TOTAL BUT PAYMENTS RECEIVED")
        print("=" * 80)
        
        # Find charters with $0 total but payments
        cur.execute("""
            SELECT 
                charter_id,
                reserve_number,
                charter_date,
                total_amount_due,
                paid_amount,
                balance
            FROM charters
            WHERE (total_amount_due = 0 OR total_amount_due IS NULL)
              AND paid_amount > 0
            ORDER BY paid_amount DESC
        """)
        
        charters = cur.fetchall()
        
        if not charters:
            print("\n✓ No charters need fixing")
            return
        
        print(f"\n📊 Found {len(charters)} charters with $0 total but payments")
        
        total_to_fix = sum(c[4] for c in charters)
        print(f"   Total paid amount: ${total_to_fix:,.2f}")
        
        # Show top 20
        print(f"\n📋 TOP 20:")
        print(f"\n{'Reserve':<10} {'Date':<12} {'Total':>12} {'Paid':>12} {'Balance':>12}")
        print("-" * 70)
        
        for i, (charter_id, reserve, charter_date, total, paid, balance) in enumerate(charters[:20]):
            date_str = str(charter_date) if charter_date else "N/A"
            print(f"{reserve:<10} {date_str:<12} ${total or 0:>10,.2f} ${paid or 0:>10,.2f} ${balance or 0:>10,.2f}")
        
        if args.write:
            # Create backup
            charter_ids = [c[0] for c in charters]
            print(f"\n📦 Creating backup...")
            backup_name = create_backup_before_delete(
                cur,
                'charters',
                condition=f"charter_id IN ({','.join(map(str, charter_ids))})"
            )
            print(f"   ✓ Backup: {backup_name}")
            
            # Update total_amount_due to match paid_amount
            print(f"\n🔄 Updating {len(charters)} charters...")
            cur.execute(f"""
                UPDATE charters
                SET total_amount_due = paid_amount,
                    balance = 0
                WHERE charter_id IN ({','.join(map(str, charter_ids))})
            """)
            updated_count = cur.rowcount
            
            conn.commit()
            
            print(f"   ✓ Updated {updated_count:,} charters")
            print(f"   ✓ Set total_amount_due = paid_amount")
            print(f"   ✓ Set balance = $0")
            
            # Verify
            cur.execute("""
                SELECT COUNT(*), SUM(balance)
                FROM charters
                WHERE balance < 0
            """)
            neg_count, neg_sum = cur.fetchone()
            
            print(f"\n📊 REMAINING NEGATIVE BALANCES:")
            print(f"   Count: {neg_count:,}")
            print(f"   Total credits: ${abs(neg_sum or 0):,.2f}")
            
        else:
            print("\n" + "=" * 80)
            print("DRY RUN MODE")
            print("=" * 80)
            print(f"\nWould update {len(charters)} charters:")
            print(f"  - Set total_amount_due = paid_amount")
            print(f"  - Set balance = $0")
            print(f"  - Total adjustment: ${total_to_fix:,.2f}")
            print("\nTo apply fixes, run with: --write")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[FAIL] Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
