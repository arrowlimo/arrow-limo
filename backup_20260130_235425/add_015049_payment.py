#!/usr/bin/env python3
"""
Add balancing payment to 015049 ($262.50 cash payment).
Keep 015978 as legitimate aged receivable.
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REDACTED***")
cur = conn.cursor()

print("Adding balancing payment to 015049...")
print()

# Add $262.50 cash payment to 015049
try:
    cur.execute("""
        INSERT INTO payments (reserve_number, payment_method, amount, payment_date, created_at, notes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, ('015049', 'cash', 262.50, '2019-11-28', datetime.now(), 'Driver own run - balanced'))
    
    # Verify
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '015049'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '015049'), 0) as payments
    """)
    charges, payments = cur.fetchone()
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    
    print(f"✓ Added $262.50 cash payment to 015049")
    print(f"  Balance: ${balance:.2f}")
except Exception as e:
    print(f"✗ Error: {e}")

print()
print("015978 status: Legitimate aged receivable ($612.02) - keeping as-is")

conn.commit()
print()
print("✅ Done")

cur.close()
conn.close()
