"""
Remove erroneous charter_charges from 2025-07-24 batch import
These charges were added for charters with $0 LMS Est_Charge (UNCLOSED/CLOSED status)
Total impact: ~$17,201 in invalid charges across 15 charters

Safety: Creates backup before deletion
"""
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

# Charters with $0 LMS Est_Charge but have PG charges from bad 2025-07-24 import
ZERO_EST_RESERVES = [
    '016593', '013603', '015542', '015541', '017737', 
    '017483', '015152', '016417', '016296', '017042',
    '018198', '017041', '017070', '015189', '015194',
    '015427', '015463', '017286', '016410', '016868'
]

def main():
    write_mode = '--write' in sys.argv
    
    print("="*110)
    print("REMOVE ERRONEOUS CHARTER_CHARGES FROM 2025-07-24 BATCH IMPORT")
    print("="*110)
    print("\nContext: These charters have $0 LMS Est_Charge (UNCLOSED/CLOSED/CANCELLED status)")
    print("         Charges were incorrectly added on 2025-07-24 in same batch as duplicate payments")
    
    if not write_mode:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("   Run with --write to apply changes\n")
    
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all charters (with or without charges)
    cur.execute("""
        SELECT c.reserve_number, c.charter_id, c.total_amount_due,
               cc.charge_id, cc.description, cc.amount, cc.created_at
        FROM charters c
        LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
        WHERE c.reserve_number = ANY(%s)
        ORDER BY c.reserve_number, cc.created_at
    """, (ZERO_EST_RESERVES,))
    
    charges = cur.fetchall()
    
    # Group by charter
    charter_charges = {}
    for row in charges:
        reserve = row['reserve_number']
        if reserve not in charter_charges:
            charter_charges[reserve] = {
                'charter_id': row['charter_id'],
                'total_amount_due': row['total_amount_due'],
                'charges': []
            }
        if row['charge_id']:  # Only add if charge exists
            charter_charges[reserve]['charges'].append({
                'charge_id': row['charge_id'],
                'description': row['description'],
                'amount': row['amount'],
                'created_at': row['created_at']
            })
    
    print(f"{'Reserve':<10}{'Charter_ID':<12}{'Current_Total':>14}{'Charges':>10}{'Action':<40}")
    print("-"*110)
    
    total_charters = 0
    total_charges_deleted = 0
    total_amount_removed = 0.0
    
    for reserve in sorted(charter_charges.keys()):
        data = charter_charges[reserve]
        charter_id = data['charter_id']
        current_total = float(data['total_amount_due'] or 0)
        charge_count = len(data['charges'])
        charge_sum = float(sum(c['amount'] for c in data['charges']))
        
        if charge_count > 0:
            action = f"DELETE {charge_count} charges, set total=0"
        else:
            action = f"No charges, just set total=0"
        print(f"{reserve:<10}{charter_id:<12}{current_total:14.2f}{charge_count:10}{action:<40}")
        
        if write_mode:
            # Create backup of charter_charges
            if total_charters == 0:  # First charter, create backup
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'charter_charges_backup_{timestamp}'
                cur.execute(f"""
                    CREATE TABLE {backup_name} AS 
                    SELECT * FROM charter_charges 
                    WHERE charter_id IN (
                        SELECT charter_id FROM charters WHERE reserve_number = ANY(%s)
                    )
                """, (ZERO_EST_RESERVES,))
                print(f"\n✓ Backup created: {backup_name}")
            
            # Delete charter_charges if any exist
            if charge_count > 0:
                cur.execute("DELETE FROM charter_charges WHERE charter_id = %s", (charter_id,))
                deleted = cur.rowcount
            else:
                deleted = 0
            
            # Update charter totals to $0
            cur.execute("""
                UPDATE charters 
                SET total_amount_due = 0,
                    balance = 0 - COALESCE(paid_amount, 0)
                WHERE charter_id = %s
            """, (charter_id,))
            
            total_charges_deleted += deleted
            total_amount_removed += charge_sum
        else:
            total_charges_deleted += charge_count
            total_amount_removed += charge_sum
        
        total_charters += 1
    
    print("\n" + "="*110)
    print("SUMMARY")
    print("="*110)
    print(f"Charters processed: {total_charters}")
    print(f"Charter_charges deleted: {total_charges_deleted}")
    print(f"Total amount removed: ${total_amount_removed:,.2f}")
    
    if write_mode:
        conn.commit()
        print("\n✓ Changes committed to database")
        print("\nNext Steps:")
        print("  1. Re-run list_total_amount_due_discrepancies.py to verify gap reduction")
        print(f"  2. Expected gap reduction: ${total_amount_removed:,.2f}")
        print(f"  3. New expected gap: $25,204 - ${total_amount_removed:,.2f} = ${25204 - total_amount_removed:,.2f}")
    else:
        print("\n⚠️  DRY RUN - No changes made. Run with --write to apply.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
