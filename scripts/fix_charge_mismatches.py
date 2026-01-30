"""
Fix charters where total_amount_due doesn't match SUM(charter_charges.amount).
Recalculate total_amount_due from actual charge records.
"""
import psycopg2
from decimal import Decimal
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def fix_charge_mismatches(apply=False):
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("FIXING CHARGE MISMATCHES")
    print("=" * 100)
    
    # Find charters with charge mismatches
    cur.execute("""
        WITH charge_sums AS (
            SELECT 
                charter_id,
                SUM(amount) as actual_charges
            FROM charter_charges
            GROUP BY charter_id
        )
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            cs.actual_charges,
            c.total_amount_due - cs.actual_charges as difference,
            c.paid_amount,
            c.balance
        FROM charters c
        INNER JOIN charge_sums cs ON c.charter_id = cs.charter_id
        WHERE ABS(c.total_amount_due - cs.actual_charges) > 0.01
        ORDER BY ABS(c.total_amount_due - cs.actual_charges) DESC
    """)
    
    mismatches = cur.fetchall()
    
    if not mismatches:
        print("\n✓ No charge mismatches found!")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(mismatches)} charters with charge mismatches")
    
    total_difference = sum(abs(row[5]) for row in mismatches)
    print(f"Total absolute difference: ${total_difference:,.2f}")
    
    print("\nSample mismatches (first 10):")
    for i, row in enumerate(mismatches[:10], 1):
        charter_id, reserve_number, charter_date, total_due, actual_charges, diff, paid, balance = row
        print(f"\n{i}. Reserve {reserve_number}:")
        print(f"   Current total_amount_due: ${total_due:,.2f}")
        print(f"   Actual charges sum: ${actual_charges:,.2f}")
        print(f"   Difference: ${diff:,.2f}")
        print(f"   Paid: ${paid or 0:,.2f}, Balance: ${balance or 0:,.2f}")
    
    if not apply:
        print("\n" + "=" * 100)
        print("DRY RUN - No changes made")
        print("=" * 100)
        print(f"\nWould update {len(mismatches)} charters:")
        print(f"  - Recalculate total_amount_due from SUM(charter_charges.amount)")
        print(f"  - Recalculate balance = total_amount_due - paid_amount")
        print(f"  - Total adjustment: ${total_difference:,.2f}")
        print("\nRun with --apply to make changes")
        cur.close()
        conn.close()
        return
    
    # Create backup
    print("\n" + "=" * 100)
    print("CREATING BACKUP...")
    print("=" * 100)
    
    charter_ids = [row[0] for row in mismatches]
    placeholders = ','.join(['%s'] * len(charter_ids))
    
    import datetime
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_backup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM charters 
        WHERE charter_id IN ({placeholders})
    """, charter_ids)
    
    print(f"✓ Backup created: {backup_table} ({len(mismatches)} rows)")
    
    # Apply fixes
    print("\n" + "=" * 100)
    print("APPLYING FIXES...")
    print("=" * 100)
    
    updated_count = 0
    total_adjustment = Decimal('0')
    
    for row in mismatches:
        charter_id, reserve_number, _, current_total, actual_charges, diff, paid_amount, _ = row
        
        # Calculate new balance
        new_balance = actual_charges - (paid_amount or Decimal('0'))
        
        cur.execute("""
            UPDATE charters 
            SET total_amount_due = %s,
                balance = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (actual_charges, new_balance, charter_id))
        
        updated_count += 1
        total_adjustment += abs(diff)
    
    conn.commit()
    
    print(f"✓ Successfully updated {updated_count} charters")
    print(f"  Total adjustment: ${total_adjustment:,.2f}")
    
    # Verify fixes
    print("\n" + "=" * 100)
    print("VERIFYING FIXES...")
    print("=" * 100)
    
    cur.execute("""
        WITH charge_sums AS (
            SELECT 
                charter_id,
                SUM(amount) as actual_charges
            FROM charter_charges
            GROUP BY charter_id
        )
        SELECT COUNT(*)
        FROM charters c
        INNER JOIN charge_sums cs ON c.charter_id = cs.charter_id
        WHERE ABS(c.total_amount_due - cs.actual_charges) > 0.01
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("[OK] VERIFICATION PASSED - All charge mismatches resolved!")
    else:
        print(f"[WARN] WARNING - {remaining} mismatches still remain")
    
    print("\n" + "=" * 100)
    print("BACKUP INFO:")
    print(f"  Table: {backup_table}")
    print(f"  Rows: {len(mismatches)}")
    print(f"  To restore: INSERT INTO charters SELECT * FROM {backup_table} ON CONFLICT (charter_id) DO UPDATE SET ...")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix charge mismatches')
    parser.add_argument('--apply', action='store_true', help='Apply fixes (default is dry-run)')
    args = parser.parse_args()
    
    fix_charge_mismatches(apply=args.apply)
