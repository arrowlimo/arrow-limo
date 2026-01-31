"""
Check LMS for correct status of reserves 019685 and 019687.
These show as 'refund_pair' in PostgreSQL but have no payments/charges.
"""

import pyodbc
import sys

LMS_PATH = r'L:\limo\backups\lms.mdb'

def check_lms_status():
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    try:
        conn = pyodbc.connect(conn_str)
    except Exception as e:
        print(f"ERROR: Cannot connect to LMS: {e}")
        sys.exit(1)
    
    cur = conn.cursor()
    
    reserves = ['019685', '019687']
    
    print("=" * 100)
    print("LMS RESERVE TABLE DATA")
    print("=" * 100)
    
    for reserve in reserves:
        cur.execute("""
            SELECT Reserve_No, PU_Date, Name, Rate, Balance, Deposit, 
                   Est_Charge, Status, Cancelled, Notes
            FROM Reserve
            WHERE Reserve_No = ?
        """, (reserve,))
        
        row = cur.fetchone()
        if row:
            print(f"\nReserve: {row[0]}")
            print(f"  Date: {row[1]}")
            print(f"  Client: {row[2]}")
            print(f"  Rate: ${row[3] or 0:,.2f}")
            print(f"  Balance: ${row[4] or 0:,.2f}")
            print(f"  Deposit: ${row[5] or 0:,.2f}")
            print(f"  Est_Charge: ${row[6] or 0:,.2f}")
            print(f"  Status: {row[7] or 'NULL'}")
            print(f"  Cancelled: {row[8]}")
            print(f"  Notes: {row[9] or 'None'}")
        else:
            print(f"\n{reserve}: NOT FOUND in LMS")
    
    print("\n" + "=" * 100)
    print("LMS PAYMENT TABLE DATA")
    print("=" * 100)
    
    for reserve in reserves:
        cur.execute("""
            SELECT Reserve_No, Amount, [Key], LastUpdated
            FROM Payment
            WHERE Reserve_No = ?
        """, (reserve,))
        
        payments = cur.fetchall()
        if payments:
            print(f"\n{reserve} has {len(payments)} payment(s):")
            for p in payments:
                print(f"  ${p[1] or 0:,.2f} - Key: {p[2]} - Date: {p[3]}")
        else:
            print(f"\n{reserve}: NO PAYMENTS in LMS")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    check_lms_status()
