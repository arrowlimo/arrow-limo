#!/usr/bin/env python3
"""
Debug why charter 019404 still shows wrong paid_amount after recalculation.
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
print("DEBUG CHARTER 019404 RECALCULATION")
print("=" * 80)

# 1. Get charter info
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, cancelled
    FROM charters
    WHERE reserve_number = '019404'
""")
charter = cur.fetchone()

print(f"\n📊 CHARTER 019404 CURRENT STATE:")
print(f"   Charter ID: {charter['charter_id']}")
print(f"   Reserve: {charter['reserve_number']}")
print(f"   Total due: ${charter['total_amount_due'] or 0:.2f}")
print(f"   Paid amount: ${charter['paid_amount'] or 0:.2f}")
print(f"   Balance: ${charter['balance'] or 0:.2f}")
print(f"   Cancelled: {charter['cancelled']}")

# 2. Check actual payments by reserve_number
cur.execute("""
    SELECT 
        payment_id, 
        amount, 
        payment_date, 
        charter_id,
        CASE WHEN charter_id IS NULL THEN 'UNLINKED' ELSE 'LINKED' END as status
    FROM payments
    WHERE reserve_number = '019404'
    ORDER BY payment_date
""")
payments = cur.fetchall()

print(f"\n💰 PAYMENTS WITH RESERVE 019404:")
total_payments = 0
for p in payments:
    print(f"   Payment {p['payment_id']}: ${p['amount']:.2f} on {p['payment_date']}, {p['status']}")
    total_payments += p['amount']
print(f"   TOTAL: ${total_payments:.2f}")

# 3. Check if charter was in the backup (meaning it WAS updated)
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM charters_backup_20251111_210447
    WHERE reserve_number = '019404'
""")
in_backup = cur.fetchone()

print(f"\n📦 WAS CHARTER IN BACKUP?")
print(f"   In backup: {in_backup['cnt'] > 0}")

if in_backup['cnt'] > 0:
    cur.execute("""
        SELECT paid_amount, balance
        FROM charters_backup_20251111_210447
        WHERE reserve_number = '019404'
    """)
    old = cur.fetchone()
    print(f"   OLD paid_amount: ${old['paid_amount'] or 0:.2f}")
    print(f"   OLD balance: ${old['balance'] or 0:.2f}")
    print(f"   CURRENT paid_amount: ${charter['paid_amount'] or 0:.2f}")
    print(f"   CURRENT balance: ${charter['balance'] or 0:.2f}")
    
    if abs((old['paid_amount'] or 0) - (charter['paid_amount'] or 0)) > 0.01:
        print(f"   [OK] Charter WAS updated")
    else:
        print(f"   [FAIL] Charter was NOT updated")

# 4. What SHOULD the values be?
print(f"\n🔍 CORRECT VALUES:")
print(f"   Total due: ${charter['total_amount_due'] or 0:.2f}")
print(f"   Actual payments: ${total_payments:.2f}")
print(f"   Correct balance: ${(charter['total_amount_due'] or 0) - total_payments:.2f}")

# 5. The issue
print(f"\n[FAIL] THE PROBLEM:")
if charter['cancelled']:
    print(f"   Charter is CANCELLED")
    print(f"   Total due should be: $0.00 (cancelled)")
    print(f"   Payments are: ${total_payments:.2f}")
    if total_payments > 0:
        print(f"   These payments should be REFUNDED or applied to another charter")
    print(f"   Balance should show: $-{total_payments:.2f} (credit to customer)")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("✓ Debug complete")
print("=" * 80)
