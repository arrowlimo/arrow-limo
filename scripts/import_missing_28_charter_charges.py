"""
Import missing charter_charges for 28 charters from LMS
These charters have total_amount_due = 0 because charter_charges were never imported
LMS Est_Charge totals to $29,217.70 across these 28 charters
"""
import os, sys
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

LMS_PATH_PRIMARY = r'L:\limo\lms.mdb'
LMS_PATH_BACKUP = r'L:\limo\backups\lms.mdb'

# 28 charters with missing charges
MISSING_CHARTERS = [
    (18658, '019743'), (18656, '019746'), (18660, '019739'), (18659, '019744'),
    (18661, '019736'), (18662, '019719'), (18663, '019732'), (18664, '019734'),
    (18666, '019741'), (18665, '019742'), (18667, '019740'), (18668, '019738'),
    (18672, '019726'), (18673, '019728'), (18674, '019727'), (18685, '019717'),
    (18681, '019722'), (18682, '019721'), (18683, '019720'), (18657, '019745'),
    (18669, '019737'), (18670, '019733'), (18671, '019735'), (18677, '019723'),
    (18678, '019731'), (18679, '019725'), (18680, '019724'), (18684, '019718'),
]

def connect_pg():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def connect_lms():
    for path in (LMS_PATH_PRIMARY, LMS_PATH_BACKUP):
        if not os.path.exists(path):
            continue
        try:
            return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};')
        except:
            try:
                return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb)}};DBQ={path};')
            except Exception as e:
                print(f"Failed Access connect for {path}: {e}")
    raise RuntimeError("Could not connect to any LMS .mdb path")

def main():
    write_mode = '--write' in sys.argv
    
    print("="*110)
    print("IMPORT MISSING CHARTER_CHARGES FROM LMS (28 CHARTERS)")
    print("="*110)
    
    if not write_mode:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
        print("   Run with --write to apply changes\n")
    
    lms_conn = connect_lms()
    lms_cur = lms_conn.cursor()
    
    pg_conn = connect_pg()
    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)
    
    total_imported = 0
    total_amount = Decimal('0.00')
    
    for charter_id, reserve_no in MISSING_CHARTERS:
        # Get Est_Charge from LMS
        lms_cur.execute("SELECT Est_Charge, Rate FROM Reserve WHERE Reserve_No = ?", (reserve_no,))
        lms_row = lms_cur.fetchone()
        
        if not lms_row:
            print(f"✗ {reserve_no}: Not found in LMS")
            continue
        
        est_charge = float(lms_row.Est_Charge) if lms_row.Est_Charge else 0.0
        rate = float(lms_row.Rate) if lms_row.Rate else 0.0
        
        if est_charge <= 0:
            print(f"⊙ {reserve_no}: LMS Est_Charge is $0.00, skipping")
            continue
        
        # Create single charter_charge entry matching Est_Charge
        description = f"Charter total (from LMS Est_Charge import)"
        
        print(f"✓ {reserve_no} (charter_id={charter_id}): Importing ${est_charge:.2f}")
        
        if write_mode:
            try:
                pg_cur.execute("""
                    INSERT INTO charter_charges (charter_id, description, amount, created_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                """, (charter_id, description, est_charge))
                
                # Update charter total_amount_due and balance
                pg_cur.execute("""
                    UPDATE charters
                    SET total_amount_due = %s,
                        balance = %s - COALESCE(paid_amount, 0)
                    WHERE charter_id = %s
                """, (est_charge, est_charge, charter_id))
                
                total_imported += 1
                total_amount += Decimal(str(est_charge))
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
        else:
            total_imported += 1
            total_amount += Decimal(str(est_charge))
    
    print("\n" + "="*110)
    print("SUMMARY")
    print("="*110)
    print(f"Charters processed: {len(MISSING_CHARTERS)}")
    print(f"Charges imported: {total_imported}")
    print(f"Total amount: ${total_amount:,.2f}")
    
    if write_mode:
        pg_conn.commit()
        print("\n✓ Changes committed to database")
        print("\nNext Step: Re-run list_total_amount_due_discrepancies.py to verify gap reduction")
    else:
        print("\n⚠️  DRY RUN - No changes made. Run with --write to apply.")
    
    pg_cur.close()
    pg_conn.close()
    lms_cur.close()
    lms_conn.close()

if __name__ == '__main__':
    main()
