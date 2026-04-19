import pyodbc

LMS_PATH = r"l:\lms2026c.mdb"
conn_str = rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

print("Checking LMS for 001820...\n")

# Method 1: Get ALL reserves and filter in Python
lms_cur.execute("SELECT Res_No FROM Reserve")
all_reserves = [r.Res_No for r in lms_cur.fetchall()]
print(f"1. Reserve 001820 in LMS: {'YES' if '001820' in all_reserves else 'NO'}")
print(f"   (Total reserves in LMS: {len(all_reserves)})")

# Method 2: Get ALL payments and filter
lms_cur.execute("SELECT PaymentID, Amount, Key, Reserve_No FROM Payment")
all_payments = lms_cur.fetchall()
payments_001820 = [p for p in all_payments if p.Reserve_No == '001820']
print(f"\n2. Payments for 001820 in LMS: {len(payments_001820)} rows")
for p in payments_001820:
    print(f"   Payment#{p.PaymentID}: ${p.Amount}, Key={p.Key}")

# Method 3: List reserves near 001820
nearby_reserves = [r for r in all_reserves if '001810' <= r <= '001830']
print(f"\n3. Reserves 001810-001830 in LMS: {len(nearby_reserves)} total")
print(f"   {sorted(nearby_reserves)}")
if '001820' in nearby_reserves:
    print("   **001820 IS in this range**")
else:
    print("   **001820 is NOT in this range**")

lms_conn.close()
