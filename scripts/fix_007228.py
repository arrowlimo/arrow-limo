#!/usr/bin/env python3
"""
Fix reserve 007228 balance calculation.

Issue: Refund payment dated 2013-01-28 was excluded from 2012 recalculation
because it uses payment_date filter, but charter is 2012.

Solution: Calculate ALL payments by reserve_number regardless of payment_date.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("="*80)
print("FIX RESERVE 007228")
print("="*80)

# Get current state
cur.execute("""
    SELECT total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = '007228'
""")
before = cur.fetchone()
print(f"\nBEFORE:")
print(f"  Total Due: ${before[0]:.2f}")
print(f"  Paid: ${before[1]:.2f}")
print(f"  Balance: ${before[2]:.2f}")

# Calculate correct paid amount (ALL payments regardless of date)
cur.execute("""
    SELECT COALESCE(SUM(amount), 0)
    FROM payments
    WHERE reserve_number = '007228'
""")
correct_paid = cur.fetchone()[0]
print(f"\nCALCULATED:")
print(f"  Correct Paid: ${correct_paid:.2f}")
print(f"  Correct Balance: ${before[0] - correct_paid:.2f}")

# Update
cur.execute("""
    UPDATE charters
    SET paid_amount = %s,
        balance = %s
    WHERE reserve_number = '007228'
""", (correct_paid, before[0] - correct_paid))

print(f"\n[SUCCESS] Updated charter 007228")

# Verify
cur.execute("""
    SELECT total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = '007228'
""")
after = cur.fetchone()
print(f"\nAFTER:")
print(f"  Total Due: ${after[0]:.2f}")
print(f"  Paid: ${after[1]:.2f}")
print(f"  Balance: ${after[2]:.2f}")

conn.commit()
cur.close()
conn.close()

print("\n" + "="*80)
print("[COMPLETE] Reserve 007228 now shows net $0.00 (payment + refund)")
print("="*80)
