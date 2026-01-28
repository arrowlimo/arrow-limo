#!/usr/bin/env python3
"""
Check charter 019404 status after payment fix.
"""

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("CHARTER 019404 STATUS AFTER FIX")
print("=" * 80)

# Get charter details
cur.execute("""
    SELECT charter_id, reserve_number, charter_date, 
           total_amount_due, paid_amount, balance, cancelled,
           retainer_amount, retainer_received
    FROM charters
    WHERE reserve_number = '019404'
""")

charter = cur.fetchone()

print(f"\n📊 CHARTER DETAILS:")
print(f"   Charter ID: {charter['charter_id']}")
print(f"   Reserve: {charter['reserve_number']}")
print(f"   Date: {charter['charter_date']}")
print(f"   Total due: ${charter['total_amount_due'] or 0:.2f}")
print(f"   Paid: ${charter['paid_amount'] or 0:.2f}")
print(f"   Balance: ${charter['balance'] or 0:.2f}")
print(f"   Cancelled: {charter['cancelled']}")
print(f"   Retainer amount: ${charter['retainer_amount'] or 0:.2f}")
print(f"   Retainer received: {charter['retainer_received']}")

# Get payments with this reserve number
cur.execute("""
    SELECT payment_id, amount, payment_date, charter_id, payment_method
    FROM payments
    WHERE reserve_number = '019404'
    ORDER BY payment_date
""")

payments = cur.fetchall()

print(f"\n💰 PAYMENTS WITH RESERVE 019404: ({len(payments)} found)")
for p in payments:
    charter_status = "LINKED" if p['charter_id'] else "UNLINKED"
    print(f"   Payment {p['payment_id']}: ${p['amount']:.2f} on {p['payment_date']}, "
          f"charter_id={p['charter_id']}, {charter_status}")

# Get charges
cur.execute("""
    SELECT charge_id, description, amount
    FROM charter_charges
    WHERE charter_id = %s
""", (charter['charter_id'],))

charges = cur.fetchall()

print(f"\n💵 CHARGES: ({len(charges)} found)")
total_charges = 0
for c in charges:
    print(f"   {c['description']}: ${c['amount']:.2f}")
    total_charges += c['amount']
print(f"   TOTAL: ${total_charges:.2f}")

print("\n" + "=" * 80)
print("✓ Check complete")
print("=" * 80)

cur.close()
conn.close()
