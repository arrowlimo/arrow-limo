"""
Fix charters with missing charter_charges records.

Creates single charter_charge entries for charters that have total_amount_due
but no charter_charges records. This aligns charter_charges sum with total_amount_due.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
import argparse

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def fix_missing_charges(write_mode=False):
    """Add charter_charges for charters missing them."""
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("FIX MISSING CHARTER_CHARGES RECORDS")
    print("=" * 80)
    print()
    
    if not write_mode:
        print("⚠️  DRY-RUN MODE")
        print("   Add --write flag to execute actual fixes")
        print()
    
    # Find charters with NO charter_charges (completely missing)
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            COALESCE(cl.client_name, c.account_number, c.client_id::text) as client_name,
            c.charter_date,
            c.total_amount_due,
            c.paid_amount,
            c.balance
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_id NOT IN (SELECT DISTINCT charter_id FROM charter_charges)
        AND c.reserve_number IS NOT NULL
        AND c.total_amount_due > 0.01
        ORDER BY c.charter_date DESC NULLS LAST
    """)
    
    missing_charges = cur.fetchall()
    
    print(f"Found {len(missing_charges)} charters with NO charter_charges")
    print(f"Total amount to add: ${sum(Decimal(str(row['total_amount_due'])) for row in missing_charges):,.2f}")
    print()
    
    if not missing_charges:
        print("✅ No charters need charter_charges fixes")
        cur.close()
        conn.close()
        return
    
    # Show sample
    print("Sample charters to fix:")
    for idx, row in enumerate(missing_charges[:10], 1):
        print(f"\n{idx}. Charter {row['reserve_number']} ({row['charter_date']})")
        print(f"   Client: {row['client_name']}")
        print(f"   Total due: ${row['total_amount_due']:,.2f}")
        print(f"   Current charges: $0.00 (NO charges)")
        print(f"   Will add: ${row['total_amount_due']:,.2f}")
        print(f"   Paid: ${row['paid_amount']:,.2f}, Balance: ${row['balance']:,.2f}")
    
    if len(missing_charges) > 10:
        print(f"\n... and {len(missing_charges) - 10} more charters")
    
    if write_mode:
        print(f"\n{'='*80}")
        print("⚠️  CONFIRM FIX")
        print("=" * 80)
        print(f"\nThis will create charter_charge records for {len(missing_charges)} charters")
        print(f"Each will get a single charge entry with description 'Charter total (reconciled)'")
        print(f"\nType 'yes' to proceed, anything else to cancel:")
        
        confirmation = input("> ").strip().lower()
        
        if confirmation != 'yes':
            print("\n❌ Fix cancelled by user")
            cur.close()
            conn.close()
            return
        
        print(f"\n{'='*80}")
        print("CREATING CHARTER_CHARGES")
        print("=" * 80)
        
        created_count = 0
        total_amount_created = Decimal('0')
        
        for row in missing_charges:
            # Use full total_amount_due since charter has NO charges at all
            cur.execute("""
                INSERT INTO charter_charges (
                    charter_id,
                    description,
                    amount,
                    charge_type
                ) VALUES (%s, %s, %s, %s)
                RETURNING charge_id
            """, (
                row['charter_id'],
                'Charter total (reconciled from total_amount_due)',
                Decimal(str(row['total_amount_due'])),
                'service'
            ))
                
            charge_id = cur.fetchone()['charge_id']
            created_count += 1
            total_amount_created += Decimal(str(row['total_amount_due']))
            
            if created_count <= 10:
                print(f"  ✅ Created charge_id {charge_id} for charter {row['reserve_number']}: ${row['total_amount_due']:,.2f}")
        
        conn.commit()
        
        if created_count > 10:
            print(f"  ... created {created_count - 10} more charges")
        
        print(f"\n✅ Created {created_count} charter_charges records")
        print(f"   Total amount: ${total_amount_created:,.2f}")
        
        # Verify
        print(f"\n{'='*80}")
        print("VERIFICATION")
        print("=" * 80)
        
        cur.execute("""
            SELECT COUNT(*) as remaining
            FROM charters c
            WHERE c.charter_id NOT IN (SELECT DISTINCT charter_id FROM charter_charges)
            AND c.reserve_number IS NOT NULL
            AND c.total_amount_due > 0.01
        """)
        
        remaining = cur.fetchone()['remaining']
        print(f"\nCharters still needing fixes: {remaining}")
        
        if remaining == 0:
            print("✅ All charters now have matching charter_charges!")
        
    else:
        print(f"\n{'='*80}")
        print("DRY-RUN COMPLETE")
        print("=" * 80)
        print(f"\n✅ Would create charter_charges for {len(missing_charges)} charters")
        print(f"\nTo execute fixes:")
        print(f"  python -X utf8 scripts/fix_missing_charter_charges.py --write")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fix missing charter_charges')
    parser.add_argument('--write', action='store_true', 
                       help='Execute actual fixes (default is dry-run)')
    
    args = parser.parse_args()
    fix_missing_charges(write_mode=args.write)
