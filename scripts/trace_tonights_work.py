#!/usr/bin/env python3
"""
TRACE TONIGHT'S WORK - What did we actually do?
"""

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("TONIGHT'S WORK TRACE")
print("=" * 80)

print("\n1️⃣ WHAT WE BACKED UP (payments_backup_20251111_205437):")
cur.execute("SELECT COUNT(*) as cnt FROM payments_backup_20251111_205437")
backup_count = cur.fetchone()['cnt']
print(f"   Backed up {backup_count} payments from cancelled charters")

print("\n2️⃣ PAYMENTS WE UNLINKED FROM CHARTER 019404:")
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, charter_id
    FROM payments_backup_20251111_205437
    WHERE reserve_number = '019404'
    ORDER BY payment_date
""")
backup_payments = cur.fetchall()
print(f"   Found {len(backup_payments)} payments in backup:")
for p in backup_payments:
    print(f"     Payment {p['payment_id']}: ${p['amount']:.2f} on {p['payment_date']}")

print("\n3️⃣ CURRENT STATE OF CHARTER 019404:")
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, cancelled
    FROM charters
    WHERE reserve_number = '019404'
""")
charter = cur.fetchone()
print(f"   Charter ID: {charter['charter_id']}")
print(f"   Total due: ${charter['total_amount_due'] or 0:.2f}")
print(f"   Paid: ${charter['paid_amount'] or 0:.2f}")
print(f"   Balance: ${charter['balance'] or 0:.2f}")
print(f"   Cancelled: {charter['cancelled']}")

print("\n4️⃣ CURRENT PAYMENTS FOR 019404:")
cur.execute("""
    SELECT payment_id, amount, payment_date, charter_id
    FROM payments
    WHERE reserve_number = '019404'
    ORDER BY payment_date
""")
current_payments = cur.fetchall()
print(f"   Found {len(current_payments)} payments:")
for p in current_payments:
    status = "LINKED to charter" if p['charter_id'] else "UNLINKED (orphaned)"
    print(f"     Payment {p['payment_id']}: ${p['amount']:.2f} on {p['payment_date']}, {status}")

print("\n5️⃣ THE PROBLEM:")
print("   [WARN] Charter 019404 is CANCELLED")
print("   [WARN] But paid_amount and balance are STILL WRONG")
print("   [WARN] We unlinked payments but didn't recalculate charter.paid_amount!")

print("\n6️⃣ WHAT WE NEED TO DO:")
print("   ✓ Recalculate paid_amount for charter 019404 (should be $0 or actual payments)")
print("   ✓ Recalculate balance = total_amount_due - paid_amount")
print("   ✓ This should be done for ALL charters after unlinking payments")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("ROOT CAUSE: We unlinked payments but forgot to recalculate charter amounts!")
print("=" * 80)
