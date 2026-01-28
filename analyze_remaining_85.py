#!/usr/bin/env python3
"""Analyze remaining 85 unbalanced charters."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get remaining
cur.execute('''
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.total_amount_due,
        c.paid_amount,
        (c.total_amount_due - c.paid_amount) as balance,
        c.status,
        COUNT(p.payment_id) as pmt_count
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.total_amount_due > 0
      AND ABS(c.total_amount_due - c.paid_amount) >= 0.10
    GROUP BY c.charter_id
    ORDER BY ABS(c.total_amount_due - c.paid_amount) ASC;
''')

results = cur.fetchall()
cur.close()
conn.close()

print("\n" + "=" * 100)
print("REMAINING 85 UNBALANCED CHARTERS".center(100))
print("=" * 100)
print(f"\nTotal: {len(results)} charters")
print(f"Current Match Rate: 99.48%")
print(f"Target: 100.00%")
print(f"Remaining Gap: {len(results)} charters (0.52%)\n")

# Categorize
small = [r for r in results if abs(r[4]) < 10]  # < $10
medium = [r for r in results if 10 <= abs(r[4]) < 100]  # $10-$100
large = [r for r in results if abs(r[4]) >= 100]  # > $100

no_payments = [r for r in results if r[6] == 0]
partial_payments = [r for r in results if r[6] > 0 and r[4] > 0]
overpaid = [r for r in results if r[4] < -0.10]

print("📊 BY BALANCE SIZE:")
print(f"   Small (< $10):       {len(small):>3} charters | ${sum(abs(r[4]) for r in small):>10,.2f}")
print(f"   Medium ($10-$100):   {len(medium):>3} charters | ${sum(abs(r[4]) for r in medium):>10,.2f}")
print(f"   Large (> $100):      {len(large):>3} charters | ${sum(abs(r[4]) for r in large):>10,.2f}")

print(f"\n📊 BY ISSUE TYPE:")
print(f"   No Payments:         {len(no_payments):>3} charters | ${sum(r[2] for r in no_payments):>10,.2f}")
print(f"   Partial Payments:    {len(partial_payments):>3} charters | ${sum(r[4] for r in partial_payments):>10,.2f}")
print(f"   Overpaid:            {len(overpaid):>3} charters | ${sum(abs(r[4]) for r in overpaid):>10,.2f}")

# Show small/medium (quick fixes)
quick_fixes = [r for r in results if abs(r[4]) < 100]
print(f"\n" + "=" * 100)
print(f"🎯 QUICK FIXES ({len(quick_fixes)} charters < $100 balance):")
print("=" * 100)
print("Charter  | Reserve  | Due        | Paid       | Balance    | Pmts | Status")
print("-" * 100)

for row in sorted(quick_fixes, key=lambda r: abs(r[4])):
    charter_id, reserve, due, paid, balance, status, pmt_count = row
    reserve_str = reserve or 'N/A'
    status_str = (status[:12] if status else 'Unknown').ljust(12)
    print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>10.2f} | ${paid:>10.2f} | ${balance:>10.2f} | {pmt_count:>4} | {status_str}")

# Show large balances separately
if large:
    print(f"\n" + "=" * 100)
    print(f"🔍 LARGE BALANCES ({len(large)} charters > $100):")
    print("=" * 100)
    print("Charter  | Reserve  | Due        | Paid       | Balance    | Pmts | Status")
    print("-" * 100)
    
    for row in sorted(large, key=lambda r: abs(r[4])):
        charter_id, reserve, due, paid, balance, status, pmt_count = row
        reserve_str = reserve or 'N/A'
        status_str = (status[:12] if status else 'Unknown').ljust(12)
        print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>10.2f} | ${paid:>10.2f} | ${balance:>10.2f} | {pmt_count:>4} | {status_str}")

print("\n" + "=" * 100)
print("💡 RECOMMENDED ACTION:")
print("=" * 100)

print(f"\n1. ADJUST SMALL BALANCES ({len(small)} charters, ${sum(abs(r[4]) for r in small):,.2f}):")
print("   → Review and adjust total_amount_due to match paid_amount")
print("   → Likely minor GST calculation differences or charge entry errors")

print(f"\n2. FIND MISSING PAYMENTS ({len([r for r in medium if r[6] > 0])} medium partial, ${sum(r[4] for r in medium if r[6] > 0 and r[4] > 0):,.2f}):")
print("   → Check banking for E-transfers or cash deposits")
print("   → Match to 136 unmatched E-transfers from earlier analysis")

print(f"\n3. REVIEW LARGE BALANCES ({len(large)} charters, ${sum(abs(r[4]) for r in large):,.2f}):")
print("   → Individual investigation required")
print("   → Check charter history and payment records")

print(f"\n4. NO-PAYMENT UNKNOWNS ({len(no_payments)} charters, ${sum(r[2] for r in no_payments):,.2f}):")
print("   → Likely abandoned bookings - mark as cancelled")

print(f"\n5. OVERPAID ({len(overpaid)} charters, ${sum(abs(r[4]) for r in overpaid):,.2f}):")
print("   → Review for duplicate payments or retainers")
print("   → Adjust total_amount_due if charges were increased after payment")

print("\n" + "=" * 100 + "\n")
