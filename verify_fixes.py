#!/usr/bin/env python3
"""Verify if receivables issues from Jan 10 have been fixed."""

import psycopg2
import os

# Connect to database
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("=" * 70)
print("VERIFYING RECEIVABLES AUDIT FIXES (Jan 10, 2026)")
print("=" * 70)

# Check 1: Unpaid charters count
cur.execute('''
SELECT COUNT(*) as count_unpaid, 
       SUM(c.total_amount_due - COALESCE(p.total_paid, 0)) as outstanding_amount
FROM charters c
LEFT JOIN (
    SELECT reserve_number, SUM(amount) as total_paid
    FROM payments
    GROUP BY reserve_number
) p ON c.reserve_number = p.reserve_number
WHERE (c.total_amount_due - COALESCE(p.total_paid, 0)) > 0.01
''')
row = cur.fetchone()
count_unpaid = row[0]
outstanding = row[1] if row[1] else 0
print(f"\n[1] UNPAID CHARTERS")
print(f"    Count: {count_unpaid} charters")
print(f"    Outstanding: ${outstanding:.2f}")
print(f"    Status: {'✅ VERIFIED (363)' if count_unpaid == 363 else f'⚠️ CHANGED (now {count_unpaid})'}")

# Check 2: Negative payments
cur.execute('''
SELECT COUNT(*) as count, SUM(amount) as total_amount
FROM payments WHERE amount < 0
''')
row = cur.fetchone()
count_neg = row[0]
neg_amount = row[1] if row[1] else 0
print(f"\n[2] NEGATIVE PAYMENTS")
print(f"    Count: {count_neg} payments")
print(f"    Total Amount: ${neg_amount:.2f}")
print(f"    Status: {'✅ VERIFIED (171)' if count_neg == 171 else f'⚠️ CHANGED (now {count_neg})'}")

# Check 3: Overpaid charters  
cur.execute('''
SELECT COUNT(*) as count_overpaid,
       SUM(COALESCE(p.total_paid, 0) - c.total_amount_due) as overpay_amount
FROM charters c
LEFT JOIN (
    SELECT reserve_number, SUM(amount) as total_paid
    FROM payments
    GROUP BY reserve_number
) p ON c.reserve_number = p.reserve_number
WHERE (COALESCE(p.total_paid, 0) - c.total_amount_due) > 0.01
''')
row = cur.fetchone()
count_overpaid = row[0]
overpay = row[1] if row[1] else 0
print(f"\n[3] OVERPAID CHARTERS")
print(f"    Count: {count_overpaid} charters")
print(f"    Overpay Amount: ${overpay:.2f}")
print(f"    Status: {'✅ VERIFIED (62)' if count_overpaid == 62 else f'⚠️ CHANGED (now {count_overpaid})'}")

# Check 4: Bad debt write-offs or bankruptcy entries
cur.execute('''
SELECT COUNT(*) as count, COALESCE(SUM(gross_amount), 0) as total_amount
FROM receipts
WHERE category IN ('bad_debt', 'write_off', 'bankruptcy', 'production_company')
   OR description ILIKE '%bankruptcy%'
   OR description ILIKE '%write-off%'
   OR description ILIKE '%production%'
''')
row = cur.fetchone()
count_writeoff = row[0]
writeoff_amount = float(row[1]) if row[1] else 0
print(f"\n[4] WRITE-OFFS/BANKRUPTCY")
print(f"    Count: {count_writeoff} entries")
print(f"    Total Amount: ${writeoff_amount:.2f}")
print(f"    Status: {'❌ NOT PROCESSED' if count_writeoff == 0 else '✅ ENTRIES CREATED'}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY:")
print("=" * 70)
if count_unpaid == 363 and count_neg == 171 and count_overpaid == 62 and count_writeoff == 0:
    print("❌ NOTHING HAS BEEN FIXED")
    print("   All items remain in original state from Jan 10, 2026 audit")
else:
    print("✅ SOME CHANGES DETECTED")
    changes = []
    if count_unpaid != 363:
        changes.append(f"Unpaid charters: {count_unpaid} (was 363)")
    if count_neg != 171:
        changes.append(f"Negative payments: {count_neg} (was 171)")
    if count_overpaid != 62:
        changes.append(f"Overpaid charters: {count_overpaid} (was 62)")
    if count_writeoff > 0:
        changes.append(f"Write-offs created: {count_writeoff} entries")
    for change in changes:
        print(f"   • {change}")

conn.close()
