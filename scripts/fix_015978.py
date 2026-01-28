#!/usr/bin/env python3
"""
Fix 015978: Remove charges to match LMS (driver's own run, fixed).
"""

import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
cur = conn.cursor()

print("Fixing 015978 (driver's own run - remove charges)...")
print()

try:
    # Get charges before delete
    cur.execute("SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '015978'")
    charges = float(cur.fetchone()[0] or 0.0)
    
    # Delete charges
    cur.execute("DELETE FROM charter_charges WHERE reserve_number = '015978'")
    deleted = cur.rowcount
    
    # Verify
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '015978'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '015978'), 0) as payments
    """)
    charges_now, payments = cur.fetchone()
    charges_now, payments = float(charges_now), float(payments)
    balance = charges_now - payments
    
    print(f"✓ Deleted {deleted} rows (${charges:,.2f})")
    print(f"  Balance: ${balance:.2f}")
except Exception as e:
    print(f"✗ Error: {e}")

conn.commit()
print()
print("✅ 015978 fixed")

cur.close()
conn.close()
