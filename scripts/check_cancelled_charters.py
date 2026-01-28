"""Check Run Type and Rate Type for the 4 discrepancy charters to identify cancelled ones."""
import pyodbc
import psycopg2

# Connect to LMS
lms_conn = pyodbc.connect('DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\\limo\\backups\\lms.mdb;')
lms_cur = lms_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

discrepancies = ['015808', '016854', '019610', '019678']

print("\n" + "="*100)
print("CHECKING CANCELLED STATUS FOR DISCREPANCY CHARTERS")
print("="*100 + "\n")

for reserve_no in discrepancies:
    # Check LMS
    lms_cur.execute("""
        SELECT Reserve_No, Status, Cancelled, Est_Charge, Balance, Run_Type, Rate_Type
        FROM Reserve 
        WHERE Reserve_No = ?
    """, (reserve_no,))
    lms_row = lms_cur.fetchone()
    
    # Check PostgreSQL
    pg_cur.execute("""
        SELECT reserve_number, status, cancelled, total_amount_due, balance
        FROM charters
        WHERE reserve_number = %s
    """, (reserve_no,))
    pg_row = pg_cur.fetchone()
    
    if lms_row:
        print(f"Charter {reserve_no}:")
        print(f"  LMS:")
        print(f"    Status: {lms_row.Status}")
        print(f"    Cancelled field: {lms_row.Cancelled}")
        print(f"    Run Type: {lms_row.Run_Type}")
        print(f"    Rate Type: {lms_row.Rate_Type}")
        print(f"    Est_Charge: ${float(lms_row.Est_Charge) if lms_row.Est_Charge else 0:.2f}")
        print(f"    Balance: ${float(lms_row.Balance) if lms_row.Balance else 0:.2f}")
        
        # Check if charges exist in LMS Charge table
        lms_cur.execute("SELECT COUNT(*), SUM(Amount) FROM Charge WHERE Reserve_No = ?", (reserve_no,))
        charge_row = lms_cur.fetchone()
        print(f"    LMS Charges: {charge_row[0]} rows, ${float(charge_row[1]) if charge_row[1] else 0:.2f} total")
        
        if pg_row:
            print(f"  PostgreSQL:")
            print(f"    Status: {pg_row[1]}")
            print(f"    Cancelled: {pg_row[2]}")
            print(f"    Total Due: ${float(pg_row[3]) if pg_row[3] else 0:.2f}")
            print(f"    Balance: ${float(pg_row[4]) if pg_row[4] else 0:.2f}")
        
        # Determine if truly cancelled
        is_cancelled = (
            lms_row.Cancelled == True or
            (lms_row.Run_Type and 'cancel' in str(lms_row.Run_Type).lower()) or
            (lms_row.Rate_Type and 'cancel' in str(lms_row.Rate_Type).lower())
        )
        
        print(f"  → CANCELLED: {is_cancelled}")
        print()
    else:
        print(f"Charter {reserve_no}: NOT FOUND IN LMS")
        print()

lms_cur.close()
lms_conn.close()
pg_cur.close()
pg_conn.close()
