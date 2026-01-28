#!/usr/bin/env python3
"""
Detailed check of 017887 in almsdata vs LMS.
"""

import psycopg2
import pyodbc

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

LMS_PATH = r"L:\limo\backups\lms.mdb"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 90)
print("017887 DETAILED ANALYSIS")
print("=" * 90)
print()

# Charter info
cur.execute("""
    SELECT charter_date, status
    FROM charters
    WHERE reserve_number = '017887'
""")
row = cur.fetchone()
if row:
    charter_date, status = row
    print(f"Charter Date: {charter_date}")
    print(f"Status: {status or 'BLANK'}")
print()

# Charges
print("CHARGES in almsdata:")
cur.execute("""
    SELECT description, amount, created_at, last_updated_by
    FROM charter_charges
    WHERE reserve_number = '017887'
    ORDER BY created_at DESC
""")
charges = cur.fetchall()
total_charges = sum(float(c[1]) for c in charges)
print(f"  Total: ${total_charges:,.2f} ({len(charges)} rows)")
for desc, amt, created, updated_by in charges:
    print(f"    - {desc:<35} ${float(amt):>10.2f}  ({updated_by or 'N/A'})")

print()

# Payments
print("PAYMENTS in almsdata:")
cur.execute("""
    SELECT payment_method, amount, payment_date, notes
    FROM payments
    WHERE reserve_number = '017887'
    ORDER BY payment_date DESC
""")
payments = cur.fetchall()
total_payments = sum(float(p[1]) for p in payments)
print(f"  Total: ${total_payments:,.2f} ({len(payments)} rows)")
for method, amt, paid, notes in payments:
    method_str = method or 'unknown'
    notes_str = notes or ''
    print(f"    - {method_str:<20} ${float(amt):>10.2f}  {paid}  {notes_str}")

print()
print(f"BALANCE: ${total_charges - total_payments:,.2f} (charges ${total_charges:,.2f} - payments ${total_payments:,.2f})")

# Check LMS
print()
print("=" * 90)
print("LMS DATA:")
print("=" * 90)

lms_conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};"
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

try:
    # Get field names
    lms_cur.execute("SELECT TOP 1 * FROM Charge")
    cols = [d[0] for d in lms_cur.description] if lms_cur.description else []
    
    reserve_field = None
    amount_field = None
    desc_field = None
    for col in cols:
        cl = col.lower()
        if "reserve" in cl and ("no" in cl or "id" in cl):
            reserve_field = col
        if cl == "amount":
            amount_field = col
        if "desc" in cl or "description" in cl:
            desc_field = col
    
    if reserve_field and amount_field:
        query = f"SELECT [{reserve_field}], [{amount_field}]"
        if desc_field:
            query += f", [{desc_field}]"
        query += f" FROM Charge WHERE [{reserve_field}] = '017887' ORDER BY [{amount_field}] DESC"
        
        lms_cur.execute(query)
        lms_charges = lms_cur.fetchall()
        
        print("LMS Charges:")
        lms_charge_total = 0.0
        for row in lms_charges:
            reserve, amt, *rest = row
            lms_charge_total += float(amt or 0)
            desc_str = rest[0] if rest else ''
            print(f"  {reserve}: ${float(amt):>10.2f}  {desc_str}")
        print(f"  Total: ${lms_charge_total:,.2f}")
except Exception as e:
    print(f"Error getting charges: {e}")

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
        lms_cur.execute(f"SELECT [{reserve_field}], [{amount_field}] FROM Payment WHERE [{reserve_field}] = '017887' ORDER BY [{amount_field}] DESC")
        lms_payments = lms_cur.fetchall()
        
        print()
        print("LMS Payments:")
        lms_payment_total = 0.0
        for row in lms_payments:
            reserve, amt = row
            lms_payment_total += float(amt or 0)
            print(f"  {reserve}: ${float(amt):>10.2f}")
        print(f"  Total: ${lms_payment_total:,.2f}")
except Exception as e:
    print(f"Error getting payments: {e}")

print()
print(f"LMS BALANCE: ${lms_charge_total - lms_payment_total:,.2f}")

lms_cur.close()
lms_conn.close()
cur.close()
conn.close()
