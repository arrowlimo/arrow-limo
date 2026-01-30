"""
Import charter_charges breakdown from LMS for charters with total_amount_due but no charges.
Uses LMS Charges table to get itemized breakdown (Service Fee, Beverage, Gratuity, GST).
"""
import os
import sys
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

LMS_PATH = r'L:\limo\backups\lms.mdb'

def connect_pg():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def connect_lms():
    if not os.path.exists(LMS_PATH):
        raise RuntimeError(f"LMS file not found: {LMS_PATH}")
    try:
        return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    except:
        return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb)}};DBQ={LMS_PATH};')

def main():
    write_mode = '--write' in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])
    
    print("\n" + "="*100)
    print("IMPORT CHARTER_CHARGES FROM LMS FOR CHARTERS WITH MISSING CHARGES")
    print("="*100)
    
    if not write_mode:
        print("\n⚠️  DRY RUN - No changes will be made. Use --write to apply.\n")
    
    pg_conn = connect_pg()
    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)
    
    # Find charters with total_amount_due but no charges
    pg_cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.total_amount_due
        FROM charters c
        WHERE c.total_amount_due IS NOT NULL
          AND c.total_amount_due > 0
          AND NOT EXISTS (
              SELECT 1 FROM charter_charges cc
              WHERE cc.charter_id = c.charter_id
          )
        ORDER BY c.charter_id
    """)
    candidates = pg_cur.fetchall()
    total = len(candidates)
    
    if limit:
        candidates = candidates[:limit]
    
    print(f"Found {total} charters with amount but no charges")
    print(f"Processing {len(candidates)} charters{' (limited)' if limit else ''}\n")
    
    if not candidates:
        print("No work to do.")
        pg_cur.close(); pg_conn.close()
        return
    
    lms_conn = connect_lms()
    lms_cur = lms_conn.cursor()
    
    imported = 0
    not_found = 0
    no_charges = 0
    
    for row in candidates:
        charter_id = row['charter_id']
        reserve_no = row['reserve_number']
        pg_total = float(row['total_amount_due'])
        
        # Query LMS Charge table for charge breakdown for this reserve
        # Charge table columns: Account_no, Amount, Closed, Desc, Frozen, Note, Rate, Reserve_No, Sequence, Tag, LastUpdated, LastUpdatedBy, ChargeID
        try:
            lms_cur.execute("""
                SELECT ChargeID, Amount, [Desc], Rate, Sequence
                FROM Charge
                WHERE Reserve_No = ?
                ORDER BY Sequence
            """, (reserve_no,))
            lms_charges = lms_cur.fetchall()
        except Exception as e:
            print(f"✗ {reserve_no}: LMS query error - {e}")
            continue
        
        if not lms_charges:
            # No charges in LMS Payment table, create single line matching total_amount_due
            no_charges += 1
            print(f"⊙ {reserve_no}: No LMS Payment entries, creating single line for ${pg_total:.2f}")
            
            if write_mode:
                pg_cur.execute("""
                    INSERT INTO charter_charges (charter_id, description, amount)
                    VALUES (%s, %s, %s)
                """, (charter_id, 'Charter total (no LMS breakdown)', pg_total))
            imported += 1
            continue
        
        # Import each payment line from LMS as a charge
        # Group by payment key - each unique key is a separate charge line
        lms_total = 0.0
        charge_lines = []
        seen_keys = set()
        
        for lms_charge in lms_charges:
            charge_id = lms_charge.ChargeID or 0
            amount = float(lms_charge.Amount) if lms_charge.Amount else 0.0
            description = (lms_charge.Desc or '').strip() or f'Charge {charge_id}'
            rate = float(lms_charge.Rate) if lms_charge.Rate else 0.0
            sequence = lms_charge.Sequence or 0
            
            lms_total += amount
            charge_lines.append((description, sequence, amount))
        
        # Check if LMS total matches PostgreSQL total
        diff = abs(lms_total - pg_total)
        if diff > 0.02:
            print(f"⚠ {reserve_no}: LMS total ${lms_total:.2f} != PG total ${pg_total:.2f} (diff ${diff:.2f})")
        else:
            print(f"✓ {reserve_no}: Importing {len(charge_lines)} charges totaling ${lms_total:.2f}")
        
        if write_mode:
            for desc, seq, amt in charge_lines:
                pg_cur.execute("""
                    INSERT INTO charter_charges (charter_id, description, amount)
                    VALUES (%s, %s, %s)
                """, (charter_id, desc, amt))
        
        imported += 1
    
    if write_mode:
        pg_conn.commit()
        print(f"\n✓ COMMITTED: Imported charges for {imported} charters")
    else:
        print(f"\nDRY RUN: Would import charges for {imported} charters")
    
    print(f"  - {imported - no_charges} had LMS charge breakdown")
    print(f"  - {no_charges} had no LMS charges (single line created)")
    print(f"  - {not_found} not found in LMS")
    
    lms_cur.close(); lms_conn.close()
    pg_cur.close(); pg_conn.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
