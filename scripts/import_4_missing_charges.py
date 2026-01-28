"""
Import missing charges for the 4 overpaid charters from LMS.
These charters have payments but no charges - need to get Est_Charge from LMS.
"""
import pyodbc
import psycopg2
from decimal import Decimal
import datetime

LMS_PATH = r'L:\limo\backups\lms.mdb'

def get_pg_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def get_lms_connection():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def import_missing_charges():
    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor()
    
    lms_conn = get_lms_connection()
    lms_cur = lms_conn.cursor()
    
    print("=" * 100)
    print("IMPORTING MISSING CHARGES FROM LMS")
    print("=" * 100)
    
    reserves = ['019536', '019571', '019657', '019586']
    
    for reserve in reserves:
        # Get from PostgreSQL
        pg_cur.execute("""
            SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance
            FROM charters 
            WHERE reserve_number = %s
        """, (reserve,))
        
        pg_row = pg_cur.fetchone()
        if not pg_row:
            print(f"\n[FAIL] {reserve}: Not found in PostgreSQL")
            continue
        
        charter_id, res_num, total_due, paid, balance = pg_row
        
        # Get from LMS
        lms_cur.execute("""
            SELECT Reserve_No, Est_Charge, Rate, Balance, Deposit
            FROM Reserve 
            WHERE Reserve_No = ?
        """, (int(reserve),))
        
        lms_row = lms_cur.fetchone()
        if not lms_row:
            print(f"\n[FAIL] {reserve}: Not found in LMS")
            continue
        
        lms_reserve, lms_est_charge, lms_rate, lms_balance, lms_deposit = lms_row
        
        print(f"\n{reserve}:")
        print(f"  PostgreSQL: total=${total_due:.2f}, paid=${paid:.2f}, balance=${balance:.2f}")
        print(f"  LMS: Est_Charge=${lms_est_charge or 0:.2f}, Rate=${lms_rate or 0:.2f}, Balance=${lms_balance or 0:.2f}, Deposit=${lms_deposit or 0:.2f}")
        
        if not lms_est_charge or lms_est_charge == 0:
            print(f"  [WARN] LMS Est_Charge is $0 - cannot import")
            continue
        
        # Create charge record
        pg_cur.execute("""
            INSERT INTO charter_charges (
                charter_id,
                description,
                amount,
                charge_type,
                created_at
            ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (charter_id, f"Charter total (from LMS Est_Charge)", lms_est_charge, 'other'))
        
        # Update charter totals
        new_balance = lms_est_charge - paid
        
        pg_cur.execute("""
            UPDATE charters 
            SET total_amount_due = %s,
                balance = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE charter_id = %s
        """, (lms_est_charge, new_balance, charter_id))
        
        print(f"  ✓ Created charge: ${lms_est_charge:.2f}")
        print(f"  ✓ Updated total_amount_due: ${total_due:.2f} → ${lms_est_charge:.2f}")
        print(f"  ✓ Updated balance: ${balance:.2f} → ${new_balance:.2f}")
    
    pg_conn.commit()
    
    print("\n" + "=" * 100)
    print("IMPORT COMPLETE")
    print("=" * 100)
    
    pg_cur.close()
    pg_conn.close()
    lms_cur.close()
    lms_conn.close()

if __name__ == '__main__':
    import_missing_charges()
