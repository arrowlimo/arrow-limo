"""
Check full LMS charter details for reserves with Est_Charge=$0 but PG has charges
Determine if charters were cancelled, deleted, or have other status explaining $0
"""
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os

LMS_PATH = r'L:\limo\backups\lms.mdb'

ZERO_EST_RESERVES = [
    '016593', '013603', '015542', '015541', '017737', 
    '017483', '015152', '016417', '016296', '017042',
    '018198', '017041', '017070', '015189', '015194',
    '015427', '015463', '017286', '016410', '016868'
]

def main():
    try:
        lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    except:
        lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb)}};DBQ={LMS_PATH};')
    lms_cur = lms_conn.cursor()
    
    pg_conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )
    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)
    
    print("="*120)
    print("LMS CHARTER STATUS ANALYSIS FOR $0 EST_CHARGE CHARTERS")
    print("="*120)
    print(f"{'Reserve':<10}{'PU_Date':<12}{'Status':<12}{'Name':<20}{'Est_Charge':>12}{'PG_Total':>12}{'PG_Charges':>12}")
    print("-"*120)
    
    cancelled = []
    completed = []
    other_status = []
    
    for reserve in ZERO_EST_RESERVES:
        lms_cur.execute("""
            SELECT Reserve_No, PU_Date, Status, Name, Est_Charge, Rate, Balance, Deposit
            FROM Reserve 
            WHERE Reserve_No = ?
        """, (reserve,))
        lms = lms_cur.fetchone()
        
        if not lms:
            continue
        
        status = (lms.Status or '').strip().upper()
        name = (lms.Name or 'Unknown')[:20]
        pu_date = str(lms.PU_Date)[:10] if lms.PU_Date else 'N/A'
        lms_est = float(lms.Est_Charge) if lms.Est_Charge not in (None, '') else 0.0
        
        # Get PG data with charter_charges count
        pg_cur.execute("""
            SELECT c.total_amount_due, COUNT(cc.charge_id) as charge_count
            FROM charters c
            LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
            WHERE c.reserve_number = %s
            GROUP BY c.charter_id, c.total_amount_due
        """, (reserve,))
        pg = pg_cur.fetchone()
        
        if not pg:
            continue
        
        pg_total = float(pg['total_amount_due'] or 0.0)
        charge_count = pg['charge_count']
        
        print(f"{reserve:<10}{pu_date:<12}{status:<12}{name:<20}{lms_est:12.2f}{pg_total:12.2f}{charge_count:12}")
        
        if status in ('CANCELLED', 'CANCELED', 'CANCEL'):
            cancelled.append((reserve, pg_total, charge_count, status))
        elif status in ('COMPLETED', 'COMPLETE'):
            completed.append((reserve, pg_total, charge_count, lms_est))
        else:
            other_status.append((reserve, pg_total, charge_count, status))
    
    print("\n" + "="*120)
    print("SUMMARY")
    print("="*120)
    print(f"Total charters analyzed: {len(ZERO_EST_RESERVES)}")
    print(f"CANCELLED status: {len(cancelled)} (${sum(x[1] for x in cancelled):,.2f} should be zeroed)")
    print(f"COMPLETED status: {len(completed)} (${sum(x[1] for x in completed):,.2f} - ERROR: should have Est_Charge!)")
    print(f"Other status: {len(other_status)} (${sum(x[1] for x in other_status):,.2f})")
    
    if cancelled:
        print(f"\n✓ CANCELLED Charters (PG charges should be removed):")
        print(f"{'Reserve':<10}{'PG_Total':>12}{'Charges':>10}{'Action':<50}")
        for reserve, pg_total, charge_count, status in cancelled:
            print(f"{reserve:<10}{pg_total:12.2f}{charge_count:10}DELETE {charge_count} charter_charges, set total_amount_due=0")
    
    if completed:
        print(f"\n⚠️  COMPLETED Charters with $0 LMS Est_Charge (DATA INTEGRITY ISSUE):")
        print(f"{'Reserve':<10}{'PG_Total':>12}{'Charges':>10}{'Issue':<50}")
        for reserve, pg_total, charge_count, lms_est in completed:
            print(f"{reserve:<10}{pg_total:12.2f}{charge_count:10}LMS Est_Charge is $0 but charter COMPLETED? Check LMS data.")
    
    if other_status:
        print(f"\nOther Status:")
        for reserve, pg_total, charge_count, status in other_status:
            print(f"{reserve:<10}{status:<12}{pg_total:12.2f}{charge_count:10}")
    
    print("\nRecommended Actions:")
    print("1. DELETE charter_charges for CANCELLED charters")
    print("2. SET total_amount_due=0 and balance=0 for CANCELLED charters")
    print("3. INVESTIGATE COMPLETED charters with $0 LMS Est_Charge (possible LMS corruption)")
    
    pg_cur.close()
    pg_conn.close()
    lms_cur.close()
    lms_conn.close()

if __name__ == '__main__':
    main()
