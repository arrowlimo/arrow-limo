"""
Verify LMS Est_Charge values for charters showing $0 in discrepancy analysis
Check if Est_Charge is truly $0 or if there was a data retrieval issue
"""
import pyodbc
import psycopg2
from psycopg2.extras import RealDictCursor
import os

LMS_PATH = r'L:\limo\backups\lms.mdb'

# Top charters where PG has charges but LMS showed $0
SUSPECT_RESERVES = [
    '016593', '013603', '015542', '015541', '017737', 
    '017483', '015152', '016417', '016296', '017042',
    '018198', '017041', '017070', '015189', '015194',
    '015427', '015463', '017286', '016410', '016868'
]

def main():
    # Connect to LMS
    try:
        lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
    except:
        lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb)}};DBQ={LMS_PATH};')
    lms_cur = lms_conn.cursor()
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    pg_cur = pg_conn.cursor(cursor_factory=RealDictCursor)
    
    print("="*110)
    print("LMS EST_CHARGE VERIFICATION FOR 'PG-ADDED CHARGES'")
    print("="*110)
    print(f"{'Reserve':<10}{'LMS_Est':>12}{'LMS_Rate':>12}{'LMS_Bal':>12}{'PG_Total':>12}{'Diff':>12}{'Status':<15}")
    print("-"*110)
    
    true_lms_zero = []
    lms_has_charge = []
    
    for reserve in SUSPECT_RESERVES:
        # Get LMS data
        lms_cur.execute("SELECT Est_Charge, Rate, Balance, Status FROM Reserve WHERE Reserve_No = ?", (reserve,))
        lms = lms_cur.fetchone()
        
        if not lms:
            print(f"{reserve:<10}{'NOT FOUND IN LMS':>57}")
            continue
        
        lms_est = float(lms.Est_Charge) if lms.Est_Charge not in (None, '') else 0.0
        lms_rate = float(lms.Rate) if lms.Rate not in (None, '') else 0.0
        lms_bal = float(lms.Balance) if lms.Balance not in (None, '') else 0.0
        
        # Get PG data
        pg_cur.execute("SELECT total_amount_due FROM charters WHERE reserve_number = %s", (reserve,))
        pg = pg_cur.fetchone()
        
        if not pg:
            print(f"{reserve:<10}{lms_est:12.2f}{lms_rate:12.2f}{lms_bal:12.2f}{'NO PG REC':>12}")
            continue
        
        pg_total = float(pg['total_amount_due'] or 0.0)
        diff = pg_total - lms_est
        
        if lms_est <= 0.01:
            status = "LMS_TRULY_ZERO"
            true_lms_zero.append((reserve, pg_total, lms_est, lms_rate, lms_bal))
        else:
            status = "LMS_HAS_CHARGE!"
            lms_has_charge.append((reserve, pg_total, lms_est, diff))
        
        print(f"{reserve:<10}{lms_est:12.2f}{lms_rate:12.2f}{lms_bal:12.2f}{pg_total:12.2f}{diff:12.2f}{status:<15}")
    
    print("\n" + "="*110)
    print("SUMMARY")
    print("="*110)
    print(f"Total reserves checked: {len(SUSPECT_RESERVES)}")
    print(f"LMS truly has $0 Est_Charge: {len(true_lms_zero)} (PG charges likely errors)")
    print(f"LMS has non-zero Est_Charge: {len(lms_has_charge)} (discrepancy analysis was WRONG!)")
    
    if lms_has_charge:
        print(f"\n⚠️  CRITICAL: LMS Est_Charge was NOT $0 for {len(lms_has_charge)} charters!")
        print(f"Total LMS Est_Charge for these: ${sum(x[2] for x in lms_has_charge):,.2f}")
        print(f"Total PG total_amount_due: ${sum(x[1] for x in lms_has_charge):,.2f}")
        print(f"Net difference: ${sum(x[3] for x in lms_has_charge):,.2f}")
        print("\nDiscrepancy analysis script has a BUG in LMS data retrieval!")
    
    if true_lms_zero:
        print(f"\nLMS Est_Charge = $0 confirmed for {len(true_lms_zero)} reserves:")
        print(f"Total PG charges: ${sum(x[1] for x in true_lms_zero):,.2f}")
        print("\nThese PG charges need investigation:")
        print(f"{'Reserve':<10}{'PG_Total':>12}{'LMS_Rate':>12}{'LMS_Balance':>12}{'Issue':<30}")
        for reserve, pg_total, lms_est, lms_rate, lms_bal in true_lms_zero[:10]:
            if lms_rate > 0:
                issue = "Rate exists but Est_Charge=0?"
            elif abs(lms_bal) > 0.01:
                issue = "Balance exists but Est_Charge=0?"
            else:
                issue = "Cancelled/deleted in LMS?"
            print(f"{reserve:<10}{pg_total:12.2f}{lms_rate:12.2f}{lms_bal:12.2f}{issue:<30}")
    
    pg_cur.close()
    pg_conn.close()
    lms_cur.close()
    lms_conn.close()

if __name__ == '__main__':
    main()
