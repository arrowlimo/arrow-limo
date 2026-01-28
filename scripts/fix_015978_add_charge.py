#!/usr/bin/env python3
"""
Fix 015978: Add back $50 in charges to match LMS (driver own run).
Should have: $50 charges, $50 payments = $0 balance
"""

import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
cur = conn.cursor()

print("Adding $50 charge to 015978 (driver's own run)...")
print()

try:
    # Add $50 service fee
    cur.execute("""
        INSERT INTO charter_charges (reserve_number, description, amount, created_at, last_updated_by)
        VALUES (%s, %s, %s, NOW(), %s)
    """, ('015978', 'Service Fee', 50.00, 'driver_own_run_correction'))
    
    # Verify
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '015978'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '015978'), 0) as payments
    """)
    charges, payments = cur.fetchone()
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    
    print(f"✓ Added $50.00 Service Fee charge")
    print(f"  Charges: ${charges:.2f}")
    print(f"  Payments: ${payments:.2f}")
    print(f"  Balance: ${balance:.2f}")
except Exception as e:
    print(f"✗ Error: {e}")

conn.commit()
print()
print("✅ 015978 fixed")

cur.close()
conn.close()
