#!/usr/bin/env python3
"""
Verify current status of all 25 receivables after write-downs.
Check if they are now fixed in almsdata (balance ~0) and cross-check with LMS.
"""

import psycopg2
import pyodbc

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

LMS_PATH = r"L:\limo\backups\lms.mdb"

# All 25 original unfixed reserves
ALL_25 = [
    '015940', '014189', '017887', '001764', '015978', '014640', '005711',
    '015211', '015195', '015049', '017765', '018013', '015315', '015288',
    '015244', '015144', '017301', '017891', '013874'
]

def get_lms_balance(reserve, lms_cur):
    """Get LMS balance for a reserve."""
    charges = 0.0
    payments = 0.0
    
    try:
        lms_cur.execute("SELECT TOP 1 * FROM Charge")
        cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
        
        reserve_field = None
        amount_field = None
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
        
        if reserve_field and amount_field:
            lms_cur.execute(f"SELECT SUM([{amount_field}]) FROM Charge WHERE [{reserve_field}] = ?", (reserve,))
            row = lms_cur.fetchone()
            charges = float(row[0] or 0)
    except Exception:
        pass
    
    try:
        lms_cur.execute("SELECT TOP 1 * FROM Payment")
        cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
        
        reserve_field = None
        amount_field = None
        for col in cols:
            cl = col.lower()
            if "reserve" in cl and ("no" in cl or "id" in cl):
                reserve_field = col
            if cl == "amount":
                amount_field = col
        
        if reserve_field and amount_field:
            lms_cur.execute(f"SELECT SUM([{amount_field}]) FROM Payment WHERE [{reserve_field}] = ?", (reserve,))
            row = lms_cur.fetchone()
            payments = float(row[0] or 0)
    except Exception:
        pass
    
    return charges - payments

# Connect to almsdata
conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Connect to LMS
lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print("=" * 100)
print("VERIFICATION: Status of all 25 receivables after write-downs")
print("=" * 100)
print()

fixed_now = []
still_owed = []
negative_balance = []

for reserve in ALL_25:
    # Get almsdata
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as payments
    """, (reserve, reserve))
    alms_charges, alms_payments = cur.fetchone()
    alms_charges, alms_payments = float(alms_charges), float(alms_payments)
    alms_balance = alms_charges - alms_payments
    
    # Get LMS
    lms_balance = get_lms_balance(reserve, lms_cur)
    
    # Categorize
    if abs(alms_balance) < 1.0:
        # Fixed (balance ~0)
        fixed_now.append((reserve, alms_balance, lms_balance))
    elif alms_balance < -0.01:
        # Negative balance (overpaid/credit)
        negative_balance.append((reserve, alms_balance, lms_balance))
    else:
        # Still owed
        still_owed.append((reserve, alms_balance, lms_balance))

# Report
print("FIXED NOW (balance ~0):")
print("-" * 100)
for reserve, alms_bal, lms_bal in fixed_now:
    match = "✓" if abs(alms_bal - lms_bal) < 1.0 else "⚠"
    print(f"{match} {reserve}: ALMS=${alms_bal:>8.2f}  LMS=${lms_bal:>8.2f}")

print()
print("NEGATIVE BALANCE (credits/overpayments):")
print("-" * 100)
for reserve, alms_bal, lms_bal in negative_balance:
    match = "✓" if abs(alms_bal - lms_bal) < 1.0 else "⚠"
    print(f"{match} {reserve}: ALMS=${alms_bal:>8.2f}  LMS=${lms_bal:>8.2f}")

print()
print("STILL OWED (positive balance):")
print("-" * 100)
for reserve, alms_bal, lms_bal in still_owed:
    match = "✓" if abs(alms_bal - lms_bal) < 1.0 else "⚠"
    print(f"{match} {reserve}: ALMS=${alms_bal:>10.2f}  LMS=${lms_bal:>10.2f}")

print()
print("=" * 100)
print(f"SUMMARY:")
print(f"  Fixed now (≈$0): {len(fixed_now)}")
print(f"  Negative balance (credits): {len(negative_balance)}")
print(f"  Still owed: {len(still_owed)}")
print(f"  Total: {len(fixed_now) + len(negative_balance) + len(still_owed)} of 25")
print("=" * 100)

cur.close()
conn.close()
lms_cur.close()
lms_conn.close()
