import pyodbc
import os

# Connect to LMS
LMS_PATH = r"l:\lms2026c.mdb"
conn_str = rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

# Check the 4 reserves in LMS
for reserve_no in ['001764', '001820', '005711', '005702']:
    print(f"\n===== {reserve_no} (LMS) =====")
    
    # Get Payment records by Reserve_No directly
    try:
        lms_cur.execute("SELECT PaymentID, Amount, Key, LastUpdated FROM Payment WHERE Reserve_No = ?", reserve_no)
        payments = lms_cur.fetchall()
        print(f"Payments from LMS Payment table: {len(payments)} rows")
        for p in payments:
            print(f"  Payment#{p.PaymentID}: ${p.Amount}, Key={p.Key}, Date={p.LastUpdated}")
    except Exception as e:
        print(f"Payment lookup error: {e}")
        
    # Also try looking up by literal string format
    try:
        lms_cur.execute(f"SELECT PaymentID, Amount, Key, Reserve_No FROM Payment WHERE Reserve_No = '{reserve_no}'")
        payments = lms_cur.fetchall()
        if len(payments) > 0:
            print(f"Payments (string query): {len(payments)} rows")
            for p in payments:
                print(f"  Payment#{p.PaymentID}: ${p.Amount}, Key={p.Key}, Reserve={p.Reserve_No}")
    except Exception as e:
        print(f"String query error: {e}")

lms_conn.close()
