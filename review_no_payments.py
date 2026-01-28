#!/usr/bin/env python3
"""Review 27 no-payment charters - identify which should be cancelled."""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get no-payment charters with full details
cur.execute('''
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.total_amount_due,
        c.status,
        c.pickup_time
    FROM charters c
    WHERE c.total_amount_due > 0
      AND c.paid_amount < 0.01
      AND NOT (c.status ILIKE '%cancel%' OR c.status ILIKE '%void%')
    ORDER BY c.total_amount_due ASC;
''')

results = cur.fetchall()
cur.close()
conn.close()

print("\n" + "=" * 100)
print("27 NO-PAYMENT CHARTERS - CANCELLATION REVIEW".center(100))
print("=" * 100)
print(f"\nTotal: {len(results)} charters | ${sum(r[2] for r in results):,.2f}")
print("\nNote: Charters already marked 'cancelled'/'void' were fixed in previous step")
print("      These have status 'Closed', 'Unknown', or other non-cancelled status")
print("\n" + "=" * 100)

# Categorize by status
by_status = {}
for row in results:
    status = row[3] or 'Unknown'
    if status not in by_status:
        by_status[status] = []
    by_status[status].append(row)

print(f"\n📊 BY STATUS:")
for status, charters in sorted(by_status.items()):
    total = sum(c[2] for c in charters)
    print(f"   {status:30} {len(charters):>3} charters | ${total:>10,.2f}")

# Show details
print("\n" + "=" * 100)
print("Charter  | Reserve  | Due        | Status           | Pickup Date")
print("-" * 100)

for row in results:
    charter_id, reserve, due, status, pickup = row
    reserve_str = reserve or 'N/A'
    status_str = (status[:15] if status else 'Unknown').ljust(16)
    pickup_str = pickup.strftime('%Y-%m-%d') if pickup else 'N/A'
    print(f"{charter_id:<8} | {reserve_str:<8} | ${due:>10.2f} | {status_str} | {pickup_str:<11}")

print("\n" + "=" * 100)
print("🔍 RECOMMENDED ACTION:")
print("=" * 100)

# Identify likely cancellations
closed_no_payment = [r for r in results if r[3] and 'closed' in r[3].lower()]
unknown_no_payment = [r for r in results if r[3] and 'unknown' in r[3].lower()]
other_no_payment = [r for r in results if r not in closed_no_payment and r not in unknown_no_payment]

print(f"\n1. CLOSED with NO payments ({len(closed_no_payment)} charters, ${sum(r[2] for r in closed_no_payment):,.2f}):")
print("   → Likely should be CANCELLED (closed but never paid)")
print(f"   → Action: SET total_amount_due = 0, status = 'cancelled'")

print(f"\n2. UNKNOWN with NO payments ({len(unknown_no_payment)} charters, ${sum(r[2] for r in unknown_no_payment):,.2f}):")
print("   → Likely abandoned/no-shows")
print(f"   → Action: SET total_amount_due = 0, status = 'cancelled'")

if other_no_payment:
    print(f"\n3. OTHER statuses ({len(other_no_payment)} charters, ${sum(r[2] for r in other_no_payment):,.2f}):")
    for r in other_no_payment:
        print(f"   {r[0]}: {r[3]}")
    print("   → Manual review needed")

print(f"\n💡 SAFE AUTO-FIX:")
print(f"   Update {len(closed_no_payment) + len(unknown_no_payment)} charters")
print(f"   (Closed or Unknown status + NO payments = cancelled)")
print(f"   Impact: +{len(closed_no_payment) + len(unknown_no_payment)} charters → {99.37 + 100*(len(closed_no_payment) + len(unknown_no_payment))/16300:.2f}%")

print("\n" + "=" * 100 + "\n")
