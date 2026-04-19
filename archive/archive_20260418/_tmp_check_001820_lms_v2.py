import pyodbc

LMS_PATH = r"l:\lms2026c.mdb"
conn_str = rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

print("Checking LMS for 001820...\n")

# Method 1: Try a simple query without LIMIT
print("1. Testing Reserve table connection...")
try:
    lms_cur.execute("SELECT Res_No FROM Reserve")
    reserves = lms_cur.fetchall()
    print(f"   Success! Total reserves: {len(reserves)}")
    
    # Now filter for 001820
    res_nos = [r.Res_No for r in reserves]
    if '001820' in res_nos:
        print("   ** 001820 FOUND in Reserve table**")
    else:
        print("   ** 001820 NOT FOUND in Reserve table**")
        
    # Show nearby
    nearby = [r for r in res_nos if '001810' <= r <= '001830']
    print(f"   Nearby (001810-001830): {sorted(nearby)}")
        
except Exception as e:
    print(f"   Error: {e}")

# Method 2: Check Payment table
print("\n2. Testing Payment table connection...")
try:
    lms_cur.execute("SELECT PaymentID, Reserve_No, Amount FROM Payment")
    payments = lms_cur.fetchall()
    print(f"   Success! Total payments: {len(payments)}")
    
    # Filter for 001820
    pmt_001820 = [p for p in payments if p.Reserve_No == '001820']
    print(f"   Payments for 001820: {len(pmt_001820)}")
    for p in pmt_001820:
        print(f"     Payment#{p.PaymentID}: ${p.Amount}")
        
except Exception as e:
    print(f"   Error: {e}")

lms_conn.close()
