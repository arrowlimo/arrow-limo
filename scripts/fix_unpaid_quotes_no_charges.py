"""
Fix quotes with no charge records and no payments.
Set total_amount_due = 0 for these.
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
        password='***REDACTED***'
    )

def fix_unpaid_quotes():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("FIXING UNPAID QUOTES WITH NO CHARGE RECORDS")
    print("=" * 100)
    
    # Get quotes with total_amount_due, no charges, no payments
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.booking_status
        FROM charters c
        WHERE c.total_amount_due > 0
          AND (c.paid_amount IS NULL OR c.paid_amount = 0)
          AND c.booking_status = 'quote'
          AND NOT EXISTS (
              SELECT 1 FROM charter_charges cc 
              WHERE cc.charter_id = c.charter_id
          )
        ORDER BY c.total_amount_due DESC
    """)
    
    charters = cur.fetchall()
    
    if not charters:
        print("\n✓ No unpaid quotes without charges!")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(charters)} unpaid quotes with no charge records")
    total = sum(r[3] for r in charters)
    print(f"Total amount to zero: ${total:,.2f}")
    
    print("\nAll charters:")
    for r in charters:
        _, reserve, date, total_due, paid, balance, status = r
        print(f"  {reserve}: ${total_due:,.2f}")
    
    print(f"\nThese are all quotes that were never converted to bookings.")
    print(f"Setting total_amount_due = 0 for all {len(charters)} charters.")
    
    # Create backup
    charter_ids = [r[0] for r in charters]
    placeholders = ','.join(['%s'] * len(charter_ids))
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'charters_backup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM charters 
        WHERE charter_id IN ({placeholders})
    """, charter_ids)
    
    print(f"\n✓ Backup created: {backup_table}")
    
    # Update
    for charter_id, _, _, _, _, _, _ in charters:
        cur.execute("""
            UPDATE charters 
            SET total_amount_due = 0,
                balance = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (charter_id,))
    
    conn.commit()
    
    print(f"✓ Successfully updated {len(charters)} charters")
    print(f"  Total amount zeroed: ${total:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    fix_unpaid_quotes()
