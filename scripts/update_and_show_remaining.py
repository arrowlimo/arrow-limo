#!/usr/bin/env python3
"""
Update almsdata based on LMS findings:
1. Add $708.75 cash payment to 001764 (fully paid in LMS)
2. Add $420.40 cash payment to 005711 (fully paid in LMS)
3. Check 015978 (driver doing own run - fixed in LMS)
4. Verify 014640 (check if balanced)
"""

import psycopg2
import pyodbc
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

LMS_PATH = r"L:\limo\backups\lms.mdb"

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

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print("Updating almsdata based on LMS findings...")
print()

# 1. Add $708.75 cash payment to 001764
print("1. Adding $708.75 cash payment to 001764...")
try:
    cur.execute("""
        INSERT INTO payments (reserve_number, payment_method, amount, payment_date, created_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, ('001764', 'cash', 708.75, '2008-02-06', datetime.now(), 'Recovered from LMS - fully paid'))
    print(f"   ✓ Added $708.75 cash payment")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 2. Add $420.40 cash payment to 005711
print("2. Adding $420.40 cash payment to 005711...")
try:
    cur.execute("""
        INSERT INTO payments (reserve_number, payment_method, amount, payment_date, created_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, ('005711', 'cash', 420.40, '2011-12-21', datetime.now(), 'Recovered from LMS - fully paid'))
    print(f"   ✓ Added $420.40 cash payment")
except Exception as e:
    print(f"   ✗ Error: {e}")

# 3. Check 015978 in LMS
print("3. Checking 015978 (driver doing own run)...")
lms_bal_015978 = get_lms_balance('015978', lms_cur)
cur.execute("""
    SELECT 
        COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '015978'), 0) as charges,
        COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '015978'), 0) as payments
""")
alms_charges, alms_payments = cur.fetchone()
alms_charges, alms_payments = float(alms_charges), float(alms_payments)
alms_bal = alms_charges - alms_payments

print(f"   ALMS: Charges ${alms_charges:.2f}, Payments ${alms_payments:.2f}, Balance ${alms_bal:.2f}")
print(f"   LMS: Balance ${lms_bal_015978:.2f}")
if abs(lms_bal_015978) < 0.01:
    print(f"   → Fixed in LMS (balance ~0)")
else:
    print(f"   → Still shows balance in LMS")

# 4. Verify 014640
print("4. Verifying 014640...")
lms_bal_014640 = get_lms_balance('014640', lms_cur)
cur.execute("""
    SELECT 
        COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '014640'), 0) as charges,
        COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '014640'), 0) as payments
""")
alms_charges_2, alms_payments_2 = cur.fetchone()
alms_charges_2, alms_payments_2 = float(alms_charges_2), float(alms_payments_2)
alms_bal_2 = alms_charges_2 - alms_payments_2

print(f"   ALMS: Charges ${alms_charges_2:.2f}, Payments ${alms_payments_2:.2f}, Balance ${alms_bal_2:.2f}")
print(f"   LMS: Balance ${lms_bal_014640:.2f}")
if abs(alms_bal_2 - lms_bal_014640) < 0.01:
    print(f"   → Balanced (same in both systems)")
else:
    print(f"   → Mismatch")

conn.commit()
print()
print("✅ Updates committed")

# Now show remaining list
print()
print("=" * 90)
print("REMAINING RECEIVABLES AFTER UPDATES:")
print("=" * 90)
print()

REMAINING = ['015195', '015049', '015315', '015144', '017301', '017891', '013874']

if lms_bal_015978 > 0.01:
    REMAINING.insert(0, '015978')

if alms_bal_2 > 0.01:
    REMAINING.insert(0, '014640')

total = 0.0
for i, reserve in enumerate(REMAINING, 1):
    cur.execute("""
        SELECT 
            c.charter_date,
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as payments
        FROM charters c
        WHERE c.reserve_number = %s
    """, (reserve, reserve, reserve))
    
    row = cur.fetchone()
    if not row:
        print(f"{i:2d}. {reserve} | NOT FOUND")
        continue
    
    charter_date, charges, payments = row
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    total += balance
    
    print(f"{i:2d}. {reserve} | {charter_date or '?'} | Charges: ${charges:>10.2f} | Payments: ${payments:>10.2f} | Balance: ${balance:>10.2f}")

print()
print(f"TOTAL REMAINING: {len(REMAINING)} reserves, ${total:,.2f} owed")

lms_cur.close()
lms_conn.close()
cur.close()
conn.close()
