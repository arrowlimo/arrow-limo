"""
Fix COMPLIANCE FIX duplicate gratuity charges.
Recalculate total_amount_due to EXCLUDE the 'customer_tip' charge_type
(which represents the duplicate non-invoiced gratuity for CRA compliance).
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

def fix_compliance_duplicates(apply=False):
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("FIXING COMPLIANCE FIX DUPLICATE GRATUITIES")
    print("=" * 100)
    
    # Find charters with customer_tip charges (the duplicates)
    cur.execute("""
        WITH customer_tips AS (
            SELECT 
                charter_id,
                SUM(amount) as tip_amount
            FROM charter_charges
            WHERE charge_type = 'customer_tip'
            GROUP BY charter_id
        ),
        all_charges AS (
            SELECT 
                charter_id,
                SUM(amount) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ),
        invoiceable_charges AS (
            SELECT 
                charter_id,
                SUM(amount) as invoiceable_amount
            FROM charter_charges
            WHERE charge_type != 'customer_tip'  -- Exclude duplicate gratuities
            GROUP BY charter_id
        )
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.total_amount_due as current_total,
            ac.total_charges as all_charges_sum,
            ic.invoiceable_amount as correct_total,
            ct.tip_amount as duplicate_gratuity,
            c.paid_amount,
            c.balance as current_balance,
            c.booking_status
        FROM charters c
        INNER JOIN customer_tips ct ON c.charter_id = ct.charter_id
        INNER JOIN all_charges ac ON c.charter_id = ac.charter_id
        INNER JOIN invoiceable_charges ic ON c.charter_id = ic.charter_id
        WHERE c.total_amount_due != ic.invoiceable_amount
        ORDER BY ct.tip_amount DESC
    """)
    
    charters = cur.fetchall()
    
    if not charters:
        print("\n✓ No COMPLIANCE FIX duplicates found!")
        cur.close()
        conn.close()
        return
    
    print(f"\nFound {len(charters)} charters with duplicate gratuity charges")
    
    total_duplicate = sum(row[6] for row in charters)
    total_adjustment = sum(abs(row[3] - row[5]) for row in charters)
    
    print(f"Total duplicate gratuity amount: ${total_duplicate:,.2f}")
    print(f"Total adjustment needed: ${total_adjustment:,.2f}")
    
    # Count by booking status
    status_counts = {}
    for row in charters:
        status = row[9] or 'NULL'
        if status not in status_counts:
            status_counts[status] = {'count': 0, 'amount': 0}
        status_counts[status]['count'] += 1
        status_counts[status]['amount'] += row[6]
    
    print(f"\nBreakdown by booking status:")
    for status, data in sorted(status_counts.items(), key=lambda x: x[1]['count'], reverse=True):
        print(f"  {status}: {data['count']} charters, ${data['amount']:,.2f} duplicate gratuities")
    
    print("\nSample charters (first 10):")
    for i, row in enumerate(charters[:10], 1):
        charter_id, reserve, date, current, all_sum, correct, dup_grat, paid, balance, status = row
        print(f"\n{i}. Reserve {reserve} ({status}):")
        print(f"   Current total_amount_due: ${current:,.2f}")
        print(f"   All charges (with duplicate): ${all_sum:,.2f}")
        print(f"   Correct total (without duplicate): ${correct:,.2f}")
        print(f"   Duplicate gratuity: ${dup_grat:,.2f}")
        print(f"   Adjustment: ${abs(current - correct):,.2f}")
    
    if not apply:
        print("\n" + "=" * 100)
        print("DRY RUN - No changes made")
        print("=" * 100)
        print(f"\nWould update {len(charters)} charters:")
        print(f"  - Set total_amount_due = SUM(charter_charges.amount) WHERE charge_type != 'customer_tip'")
        print(f"  - Recalculate balance = total_amount_due - paid_amount")
        print(f"  - Total adjustment: ${total_adjustment:,.2f}")
        print(f"  - Total duplicate gratuities excluded: ${total_duplicate:,.2f}")
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
        charter_id, _, _, _, _, correct_total, _, paid_amount, _, _ = row
        
        # Calculate new balance
        new_balance = correct_total - (paid_amount or Decimal('0'))
        
        cur.execute("""
            UPDATE charters 
            SET total_amount_due = %s,
                balance = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (correct_total, new_balance, charter_id))
        
        updated_count += 1
    
    conn.commit()
    
    print(f"✓ Successfully updated {updated_count} charters")
    print(f"  Total duplicate gratuities excluded: ${total_duplicate:,.2f}")
    print(f"  Total adjustment: ${total_adjustment:,.2f}")
    
    # Verify fixes
    print("\n" + "=" * 100)
    print("VERIFYING FIXES...")
    print("=" * 100)
    
    cur.execute("""
        WITH invoiceable_charges AS (
            SELECT 
                charter_id,
                SUM(amount) as invoiceable_amount
            FROM charter_charges
            WHERE charge_type != 'customer_tip'
            GROUP BY charter_id
        )
        SELECT COUNT(*)
        FROM charters c
        INNER JOIN invoiceable_charges ic ON c.charter_id = ic.charter_id
        WHERE ABS(c.total_amount_due - ic.invoiceable_amount) > 0.01
          AND EXISTS (
              SELECT 1 FROM charter_charges cc 
              WHERE cc.charter_id = c.charter_id 
                AND cc.charge_type = 'customer_tip'
          )
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("[OK] VERIFICATION PASSED - All COMPLIANCE FIX duplicates resolved!")
    else:
        print(f"[WARN] WARNING - {remaining} mismatches still remain")
    
    print("\n" + "=" * 100)
    print("BACKUP INFO:")
    print(f"  Table: {backup_table}")
    print(f"  Rows: {len(charters)}")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fix COMPLIANCE FIX duplicate gratuities')
    parser.add_argument('--apply', action='store_true', help='Apply fixes (default is dry-run)')
    args = parser.parse_args()
    
    fix_compliance_duplicates(apply=args.apply)
