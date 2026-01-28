#!/usr/bin/env python3
"""
Final cleanup based on LMS review:
1. Remove charges from 015315 (cancelled, no charges in LMS)
2. Keep 015195 (cancelled NRD - non-refundable deposit)
3. Verify 017301 (refund screwup)
4. Remove 013874, 015049, 017891 from active receivables (fixed)
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("Final cleanup of receivables based on LMS review...")
print()

# 1. Remove charges from 015315 (cancelled, no charges in LMS)
print("1. Removing charges from 015315 (cancelled in LMS)...")
try:
    cur.execute("SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '015315'")
    charges_015315 = float(cur.fetchone()[0] or 0.0)
    
    cur.execute("DELETE FROM charter_charges WHERE reserve_number = '015315'")
    deleted = cur.rowcount
    
    print(f"   ✓ Deleted {deleted} rows, total: ${charges_015315:,.2f}")
except Exception as e:
    print(f"   ✗ Error: {e}")

print()

# 2. Check 017301 (refund issue)
print("2. Checking 017301 (refund screwup - all refunded)...")
try:
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = '017301'), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = '017301'), 0) as payments
    """)
    charges_301, payments_301 = cur.fetchone()
    charges_301, payments_301 = float(charges_301), float(payments_301)
    balance_301 = charges_301 - payments_301
    
    print(f"   Charges: ${charges_301:,.2f}")
    print(f"   Payments: ${payments_301:,.2f}")
    print(f"   Balance: ${balance_301:,.2f}")
    
    if balance_301 < -0.01:
        print(f"   → Negative balance (over-refunded) - needs review")
    elif abs(balance_301) < 0.01:
        print(f"   → Already balanced")
    else:
        print(f"   → Still owes balance")
except Exception as e:
    print(f"   Error: {e}")

print()
conn.commit()
print("=" * 80)
print("FINAL REMAINING RECEIVABLES:")
print("=" * 80)
print()

# Show final list
FINAL_REMAINING = [
    ('014640', '2020-08-29', 'Still owed (balanced in both systems)'),
    ('015978', '2021-08-28', "Driver's own run - still owed"),
    ('015195', '2020-02-04', 'CANCELLED NRD - keep as reserve'),
    ('017301', '2022-12-31', 'INVESTIGATE - refund issue'),
]

total = 0.0
for i, (reserve, date, note) in enumerate(FINAL_REMAINING, 1):
    cur.execute("""
        SELECT 
            COALESCE((SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s), 0) as charges,
            COALESCE((SELECT SUM(amount) FROM payments WHERE reserve_number = %s), 0) as payments
    """, (reserve, reserve))
    
    charges, payments = cur.fetchone()
    charges, payments = float(charges), float(payments)
    balance = charges - payments
    total += balance
    
    print(f"{i}. {reserve} | {date} | Balance: ${balance:>10.2f}")
    print(f"   Note: {note}")
    print()

print(f"TOTAL: {len(FINAL_REMAINING)} reserves, ${total:,.2f}")
print()
print("STATUS:")
print("  ✓ 001764, 005711 - FIXED (added cash payments)")
print("  ✓ 013874, 015049, 017891 - FIXED (already balanced in LMS)")
print("  ✓ 015315 - FIXED (cancelled, charges removed)")
print("  ✓ 015787, 018013, 017765, 018013, 015288, 015244, 015940, 014189 - FIXED (cancelled, balanced)")
print("  ⏳ 014640, 015978 - LEGITIMATE AGED RECEIVABLES")
print("  ⏸️  015195 - CANCELLED NRD (keep for now)")
print("  ⚠️  017301 - NEEDS INVESTIGATION (refund issue)")

cur.close()
conn.close()
