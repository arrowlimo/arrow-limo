#!/usr/bin/env python3
"""
Fix mistake: Remove payment I added to 001764 (still owes in LMS).
Confirm 015049 is driver's own run and 005711 is fixed.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Correcting mistake: Removing payment from 001764 (still owes in LMS)...")
print()

# Remove the cash payment I added to 001764
print("1. Removing $708.75 cash payment from 001764...")
try:
    cur.execute("""
        DELETE FROM payments
        WHERE reserve_number = '001764' 
        AND payment_method = 'cash'
        AND amount = 708.75
        AND notes LIKE '%Recovered from LMS%'
    """)
    deleted = cur.rowcount
    
    # Verify
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '001764'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '001764'), 0) as payments
    """)
    charges, payments = cur.fetchone()
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    
    print(f"   ✓ Deleted {deleted} rows")
    print(f"   Balance now: Charges ${charges:.2f}, Payments ${payments:.2f}, Balance ${balance:.2f}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print()
print("2. Confirming driver's own run is 015049 (not 015978)...")
try:
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '015049'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '015049'), 0) as payments
    """)
    charges, payments = cur.fetchone()
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    print(f"   015049: Charges ${charges:.2f}, Payments ${payments:.2f}, Balance ${balance:.2f}")
    if abs(balance) < 0.01:
        print(f"   ✓ Driver's own run - FIXED")
except Exception as e:
    print(f"   Error: {e}")

print()
print("3. Confirming 005711 is fixed...")
try:
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '005711'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '005711'), 0) as payments
    """)
    charges, payments = cur.fetchone()
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    print(f"   005711: Charges ${charges:.2f}, Payments ${payments:.2f}, Balance ${balance:.2f}")
    if abs(balance) < 0.01:
        print(f"   ✓ FIXED - Fully paid")
except Exception as e:
    print(f"   Error: {e}")

conn.commit()
print()
print("✅ Corrections applied")

cur.close()
conn.close()
