#!/usr/bin/env python3
"""
Summary of orphaned payment deletion.

All 83 orphaned payments have been successfully deleted.
They were payments from 2025+ attached to non-existent reserve_numbers.
Backup preserved for audit trail.
"""

import psycopg2
import os
from datetime import datetime
import csv

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

# Get the orphaned payments from backup
cur.execute('''
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, payment_key
    FROM payments_backup_20260110_025229
    ORDER BY payment_date, reserve_number
''')

orphaned = cur.fetchall()
print(f"\n{'='*70}")
print(f"ORPHANED PAYMENTS DELETION SUMMARY")
print(f"{'='*70}\n")

print(f"✅ Total payments deleted: {len(orphaned)}")
print(f"💾 Backup preserved: payments_backup_20260110_025229 ({len(orphaned)} rows)")

# Group by reserve number
orphaned_by_reserve = {}
total_amount = 0
for pid, rn, amt, pdate, method, pkey in orphaned:
    if rn not in orphaned_by_reserve:
        orphaned_by_reserve[rn] = []
    orphaned_by_reserve[rn].append({
        'payment_id': pid,
        'amount': amt,
        'payment_date': pdate,
        'method': method,
        'key': pkey
    })
    total_amount += amt

print(f"\n📊 Unique reserve_numbers: {len(orphaned_by_reserve)}")
print(f"💰 Total amount deleted: ${total_amount:,.2f}")

# Analyze by payment date range
cur.execute('''
    SELECT 
        EXTRACT(YEAR FROM payment_date)::int AS year,
        EXTRACT(MONTH FROM payment_date)::int AS month,
        COUNT(*) AS count,
        SUM(amount) AS total
    FROM payments_backup_20260110_025229
    GROUP BY EXTRACT(YEAR FROM payment_date), EXTRACT(MONTH FROM payment_date)
    ORDER BY year, month
''')

print(f"\n📅 Payments by month:")
for year, month, count, total in cur.fetchall():
    month_name = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][month - 1] if month else 'Unknown'
    print(f"   {month_name} {year}: {count} payments, ${total:,.2f}")

# Analyze by payment method
cur.execute('''
    SELECT payment_method, COUNT(*) AS count, SUM(amount) AS total
    FROM payments_backup_20260110_025229
    GROUP BY payment_method
    ORDER BY count DESC
''')

print(f"\n💳 Payments by method:")
for method, count, total in cur.fetchall():
    method_display = method if method else "(none)"
    print(f"   {method_display}: {count} payments, ${total:,.2f}")

# Generate detailed backup file for reference
export_file = f"l:\\limo\\data\\orphaned_payments_deleted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
print(f"\n📋 Exporting detailed record to {export_file}...")

with open(export_file, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['payment_id', 'reserve_number', 'amount', 'payment_date', 'payment_method', 'payment_key'])
    
    for pid, rn, amt, pdate, method, pkey in orphaned:
        writer.writerow([pid, rn, amt, pdate, method, pkey])

print(f"✅ Exported {len(orphaned)} payments to CSV for audit trail")

# Verify current state
print(f"\n{'='*70}")
print(f"CURRENT DATABASE STATE")
print(f"{'='*70}\n")

cur.execute('SELECT COUNT(*) FROM payments')
print(f"✅ Total payments in database: {cur.fetchone()[0]:,}")

cur.execute('''
    SELECT COUNT(*) FROM payments 
    WHERE EXTRACT(YEAR FROM payment_date) >= 2025
''')
print(f"✅ 2025-2026 payments: {cur.fetchone()[0]:,}")

cur.execute('''
    SELECT COUNT(*) FROM payments p
    WHERE p.reserve_number IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
      )
''')
orphaned_remaining = cur.fetchone()[0]
if orphaned_remaining == 0:
    print(f"✅ Orphaned payments remaining: NONE")
else:
    print(f"⚠️  Orphaned payments remaining: {orphaned_remaining}")

print(f"\n{'='*70}\n")

cur.close()
conn.close()
