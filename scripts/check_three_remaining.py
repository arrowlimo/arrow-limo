"""
Check LMS data for the 3 remaining mismatches.
"""

import pyodbc

LMS_PATH = r'L:\limo\backups\lms.mdb'
conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
cur = conn.cursor()

CHARTERS = ['015940', '015808', '017991']

print("=" * 80)
print("LMS DATA FOR 3 REMAINING MISMATCHES")
print("=" * 80)

for reserve_no in CHARTERS:
    cur.execute("""
        SELECT Reserve_No, Est_Charge, Deposit, Balance, Cancelled, Status
        FROM Reserve
        WHERE Reserve_No = ?
    """, (reserve_no,))
    
    row = cur.fetchone()
    if row:
        print(f"\nReserve {row.Reserve_No}:")
        print(f"  Est_Charge: ${row.Est_Charge or 0:.2f}")
        print(f"  Deposit:    ${row.Deposit or 0:.2f}")
        print(f"  Balance:    ${row.Balance or 0:.2f}")
        print(f"  Cancelled:  {row.Cancelled}")
        print(f"  Status:     {row.Status}")
        
        # Check for payments
        cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Reserve_No = ?", (reserve_no,))
        payment_count, payment_sum = cur.fetchone()
        print(f"  Payments:   {payment_count or 0} totaling ${payment_sum or 0:.2f}")
    else:
        print(f"\nReserve {reserve_no}: NOT FOUND in LMS")

conn.close()
