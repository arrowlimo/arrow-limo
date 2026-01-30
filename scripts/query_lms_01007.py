#!/usr/bin/env python3
"""
Simpler LMS account structure query.
"""

import pyodbc

LMS_PATH = r"L:\limo\database_backups\lms2026.mdb"

def query_account_01007():
    """Query LMS for account 01007."""
    access_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
    access_conn = pyodbc.connect(access_conn_str)
    access_cur = access_conn.cursor()
    
    print("=" * 100)
    print("LMS ACCOUNT 01007 - STRUCTURE")
    print("=" * 100)
    
    # Get Customer records for 01007
    print("\n[1] CUSTOMER TABLE for Account 01007:")
    print("-" * 100)
    
    try:
        access_cur.execute("SELECT * FROM Customer WHERE Account_No = '01007'")
        customer_rows = access_cur.fetchall()
        
        if not customer_rows:
            print("  No records found")
        else:
            # Get column names
            customer_cols = [desc[0] for desc in access_cur.description]
            print(f"  Columns: {', '.join(customer_cols)}")
            print(f"\n  Found {len(customer_rows)} record(s):")
            
            for i, row in enumerate(customer_rows, 1):
                print(f"\n  Record {i}:")
                for col, val in zip(customer_cols, row):
                    print(f"    {col}: {val}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Get CustAdmin records for 01007
    print("\n\n[2] CUSTADMIN TABLE for Account 01007:")
    print("-" * 100)
    
    try:
        access_cur.execute("SELECT * FROM CustAdmin WHERE Account_No = '01007'")
        admin_rows = access_cur.fetchall()
        
        if not admin_rows:
            print("  No records found")
        else:
            # Get column names
            admin_cols = [desc[0] for desc in access_cur.description]
            print(f"  Columns: {', '.join(admin_cols)}")
            print(f"\n  Found {len(admin_rows)} record(s):")
            
            for i, row in enumerate(admin_rows, 1):
                print(f"\n  Record {i}:")
                for col, val in zip(admin_cols, row):
                    print(f"    {col}: {val}")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    # Get Reserves for 01007
    print("\n\n[3] RESERVE TABLE for Account 01007:")
    print("-" * 100)
    
    try:
        access_cur.execute("SELECT Reserve_No, Name, PU_Date, Total FROM Reserve WHERE Account_No = '01007' ORDER BY Reserve_No DESC")
        reserve_rows = access_cur.fetchall()
        
        if not reserve_rows:
            print("  No records found")
        else:
            print(f"  Found {len(reserve_rows)} charter(s):")
            print(f"\n  {'Reserve':<12} {'Client Name':<40} {'Pickup Date':<15} {'Total':<10}")
            print(f"  {'-'*12} {'-'*40} {'-'*15} {'-'*10}")
            
            for row in reserve_rows[:20]:  # Show first 20
                res_no = row[0]
                name = str(row[1])[:39] if row[1] else ""
                date_str = row[2].strftime('%Y-%m-%d') if row[2] else "N/A"
                total = row[3] if row[3] else 0
                print(f"  {res_no:<12} {name:<40} {date_str:<15} {total:<10.2f}")
            
            if len(reserve_rows) > 20:
                print(f"  ... and {len(reserve_rows) - 20} more")
    except Exception as e:
        print(f"  ERROR: {e}")
    
    access_conn.close()

if __name__ == '__main__':
    query_account_01007()
