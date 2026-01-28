#!/usr/bin/env python
"""Check charter 019672 in LMS Access database."""
import pyodbc

LMS_PATH = r'L:\limo\backups\lms.mdb'
conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

try:
    lms_conn = pyodbc.connect(conn_str)
    cur = lms_conn.cursor()
    
    # Query LMS Reserve table for 019672
    cur.execute("""
        SELECT Reserve_No, PU_Date, Est_Charge, Deposit, Balance, Name, Vehicle
        FROM Reserve
        WHERE Reserve_No = '019672'
    """)
    
    row = cur.fetchone()
    if row:
        print(f"LMS Reserve 019672 found:")
        print(f"  Reserve_No: {row[0]}")
        print(f"  PU_Date (Pickup Date): {row[1]}")
        print(f"  Est_Charge (Total): ${row[2]:.2f}" if row[2] else "  Est_Charge: None")
        print(f"  Deposit (Paid): ${row[3]:.2f}" if row[3] else "  Deposit: None")
        print(f"  Balance: ${row[4]:.2f}" if row[4] else "  Balance: None")
        print(f"  Name: {row[5]}" if row[5] else "  Name: None")
        print(f"  Vehicle: {row[6]}" if row[6] else "  Vehicle: None")
    else:
        print("Reserve 019672 NOT FOUND in LMS")
    
    cur.close()
    lms_conn.close()
    
except Exception as e:
    print(f"Error: {e}")
