import pyodbc

LMS_PATH = r"l:\lms2026c.mdb"
conn_str = rf"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(conn_str)
lms_cur = lms_conn.cursor()

print("Checking LMS for 001820...\n")

# Check if Reserve 001820 exists
lms_cur.execute("SELECT Res_No FROM Reserve WHERE Res_No = ?", ('001820',))
reserve = lms_cur.fetchone()
print(f"1. Reserve 001820 in LMS: {'YES' if reserve else 'NO'}")

# Check if Payment for 001820 exists
lms_cur.execute("SELECT PaymentID, Amount, Key FROM Payment WHERE Reserve_No = ?", ('001820',))
payments = lms_cur.fetchall()
print(f"\n2. Payments for 001820 in LMS: {len(payments)} rows")
for p in payments:
    print(f"   Payment#{p.PaymentID}: ${p.Amount}, Key={p.Key}")

# List reserves near 001820
lms_cur.execute("SELECT Res_No FROM Reserve WHERE Res_No >= ? AND Res_No <= ? ORDER BY Res_No", ('001810', '001830'))
reserves = lms_cur.fetchall()
print(f"\n3. Reserves 001810-001830 in LMS: {len(reserves)} total")
res_list = [r.Res_No for r in reserves]
print(f"   {res_list}")
if '001820' in res_list:
    print("   **001820 IS in this range**")
else:
    print("   **001820 is NOT in this range**")

lms_conn.close()
