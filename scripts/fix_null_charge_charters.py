"""
Fix charters that have total_amount_due but all their charge records are $0/NULL.
These are likely quotes or cancelled charters where charges were never properly entered.
Set total_amount_due = 0 and balance = 0 - paid_amount for these.
"""
import psycopg2
from decimal import Decimal
import argparse
import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def fix_null_charges(apply=False):
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("FIXING CHARTERS WITH ALL NULL/ZERO CHARGES")
    print("=" * 100)
    
    # Find charters with total_amount_due but all charges are $0/NULL
    cur.execute("""
        WITH zero_charges AS (
            SELECT 
                c.charter_id
            FROM charters c
            INNER JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE c.total_amount_due > 0
            GROUP BY c.charter_id
            HAVING COUNT(*) = COUNT(CASE WHEN cc.amount IS NULL OR cc.amount = 0 THEN 1 END)
        )
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.booking_status,
            c.cancelled,
            c.status,
            (SELECT COUNT(*) FROM charter_charges cc WHERE cc.charter_id = c.charter_id) as charge_count
        FROM charters c
        INNER JOIN zero_charges zc ON c.charter_id = zc.charter_id
        ORDER BY c.total_amount_due DESC
    """)
    
    charters = cur.fetchall()
    
    if not charters:
        print("\n✓ No charters with all-zero charges found!")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(charters)} charters with all NULL/$0 charges")
    
    total_amount = sum(row[3] for row in charters)
    print(f"Total amount_due to zero out: ${total_amount:,.2f}")
    
    # Analyze by status
    by_status = {}
    for row in charters:
        status = row[6] or 'NULL'
        if status not in by_status:
            by_status[status] = {'count': 0, 'amount': 0}
        by_status[status]['count'] += 1
        by_status[status]['amount'] += row[3]
    
    print(f"\nBreakdown by booking_status:")
    for status, data in sorted(by_status.items(), key=lambda x: x[1]['count'], reverse=True):
        print(f"  {status}: {data['count']} charters, ${data['amount']:,.2f}")
    
    print("\nSample charters (first 10):")
    for i, row in enumerate(charters[:10], 1):
        charter_id, reserve, date, total, paid, balance, b_status, cancelled, status, count = row
        print(f"\n{i}. Reserve {reserve}:")
        print(f"   Total due: ${total:,.2f}, Paid: ${paid or 0:,.2f}, Balance: ${balance or 0:,.2f}")
        print(f"   Status: {status}, Booking: {b_status}, Cancelled: {cancelled}")
        print(f"   Has {count} charge records (all $0/NULL)")
    
    if not apply:
        print("\n" + "=" * 100)
        print("DRY RUN - No changes made")
        print("=" * 100)
        print(f"\nWould update {len(charters)} charters:")
        print(f"  - Set total_amount_due = 0")
        print(f"  - Set balance = 0 - paid_amount (most will be 0, some negative if overpaid)")
        print(f"  - Total amount zeroed: ${total_amount:,.2f}")
        print("\nRun with --apply to make changes")
        cur.close()
        conn.close()
        return
    
    # Create backup
    print("\n" + "=" * 100)
    print("CREATING BACKUP...")
    print("=" * 100)
    
    charter_ids = [row[0] for row in charters]
    placeholders = ','.join(['%s'] * len(charter_ids))
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_backup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM charters 
        WHERE charter_id IN ({placeholders})
    """, charter_ids)
    
    print(f"✓ Backup created: {backup_table} ({len(charters)} rows)")
    
    # Apply fixes
    print("\n" + "=" * 100)
    print("APPLYING FIXES...")
    print("=" * 100)
    
    updated_count = 0
    
    for row in charters:
        charter_id, _, _, _, paid_amount, _, _, _, _, _ = row
        
        # New balance = 0 - paid (usually 0, but if overpaid will be negative)
        new_balance = Decimal('0') - (paid_amount or Decimal('0'))
        
        cur.execute("""
            UPDATE charters 
            SET total_amount_due = 0,
                balance = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (new_balance, charter_id))
        
        updated_count += 1
    
    conn.commit()
    
    print(f"✓ Successfully updated {updated_count} charters")
    print(f"  Total amount zeroed: ${total_amount:,.2f}")
    
    # Verify fixes
    print("\n" + "=" * 100)
    print("VERIFYING FIXES...")
    print("=" * 100)
    
    cur.execute("""
        WITH zero_charges AS (
            SELECT 
                c.charter_id
            FROM charters c
            INNER JOIN charter_charges cc ON c.charter_id = cc.charter_id
            WHERE c.total_amount_due > 0
            GROUP BY c.charter_id
            HAVING COUNT(*) = COUNT(CASE WHEN cc.amount IS NULL OR cc.amount = 0 THEN 1 END)
        )
        SELECT COUNT(*)
        FROM zero_charges
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("[OK] VERIFICATION PASSED - All NULL/zero charge issues resolved!")
    else:
        print(f"[WARN] WARNING - {remaining} issues still remain")
    
    print("\n" + "=" * 100)
    print("BACKUP INFO:")
    print(f"  Table: {backup_table}")
    print(f"  Rows: {len(charters)}")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix charters with all NULL/zero charges')
    parser.add_argument('--apply', action='store_true', help='Apply fixes (default is dry-run)')
    args = parser.parse_args()
    
    fix_null_charges(apply=args.apply)
