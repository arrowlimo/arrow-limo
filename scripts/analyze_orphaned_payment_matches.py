#!/usr/bin/env python3
"""
Analyze orphaned payments to find potential correct reserve_numbers.

Strategy:
1. Check if the 19773, 19774, 19775, etc. reserve numbers exist in LMS
2. If they don't exist, these might be test/demo charters
3. Search for charters with similar amounts/dates that are unpaid
4. Export detailed matching candidates
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
print(f"Analyzing {len(orphaned)} orphaned payments...\n")

# Group by reserve number to understand the data
orphaned_by_reserve = {}
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

print(f"Found {len(orphaned_by_reserve)} unique reserve_numbers in orphaned set\n")

# Check if any of these reserve numbers exist in charters
print("Checking if orphaned reserve_numbers exist in charters table:\n")
missing_reserves = []
existing_reserves = []

for rn in sorted(orphaned_by_reserve.keys()):
    cur.execute('SELECT COUNT(*) FROM charters WHERE reserve_number = %s', (rn,))
    exists = cur.fetchone()[0] > 0
    
    if exists:
        existing_reserves.append(rn)
        print(f"  ✅ {rn} EXISTS in charters")
    else:
        missing_reserves.append(rn)
        print(f"  ❌ {rn} MISSING (not in charters table)")

print(f"\nSummary:")
print(f"  Reserves that exist: {len(existing_reserves)}")
print(f"  Reserves that don't exist: {len(missing_reserves)}")

if missing_reserves:
    print(f"\n⚠️  {len(missing_reserves)} reserve_numbers have no charter records:")
    for rn in missing_reserves:
        payments = orphaned_by_reserve[rn]
        total = sum(p['amount'] for p in payments)
        print(f"    {rn}: {len(payments)} payment(s), total ${total:.2f}")

# For missing reserves, check LMS for any hints (if table exists)
print("\n" + "="*70)
print("Checking LMS staging for clues about missing reserves:\n")

try:
    cur.execute('''
        SELECT DISTINCT reserve_number 
        FROM lms_staging_reserves
        WHERE reserve_number IN (SELECT DISTINCT reserve_number 
                                 FROM payments_backup_20260110_025229)
        ORDER BY reserve_number
    ''')

    lms_reserves = [r[0] for r in cur.fetchall()]
    if lms_reserves:
        print(f"Found {len(lms_reserves)} reserve_numbers in LMS:")
        for rn in lms_reserves:
            print(f"  {rn}")
    else:
        print("No matching reserve_numbers found in LMS staging!")
except Exception as e:
    print(f"LMS staging check skipped: {e}")
    conn.rollback()  # Clear the transaction error

# Now look for unpaid charters with similar amounts near these dates
print("\n" + "="*70)
print("Finding potential matching charters (unpaid, similar amounts):\n")

matching_candidates = []
for orphan_rn, payments in orphaned_by_reserve.items():
    total_amount = sum(p['amount'] for p in payments)
    min_date = min(p['payment_date'] for p in payments)
    max_date = max(p['payment_date'] for p in payments)
    
    # Look for charters that are unpaid and have similar amounts
    cur.execute('''
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.client_name,
               COALESCE(c.total_amount_due, 0) AS amount_due,
               (SELECT COUNT(*) FROM payments WHERE charter_id = c.charter_id) AS payment_count,
               (SELECT SUM(amount) FROM payments WHERE charter_id = c.charter_id) AS paid_amount
        FROM charters c
        WHERE COALESCE(c.total_amount_due, 0) > 0
          AND (c.charter_date >= %s - INTERVAL '30 days' AND c.charter_date <= %s + INTERVAL '30 days')
          AND ABS(COALESCE(c.total_amount_due, 0) - %s) < 50
        LIMIT 5
    ''', (min_date, max_date, total_amount))
    
    candidates = cur.fetchall()
    if candidates:
        print(f"Reserve {orphan_rn} (${total_amount:.2f}, {min_date} to {max_date}):")
        for cid, cn, cdate, client, due, pcount, pamt in candidates:
            print(f"  → Charter {cid} (reserve {cn}): {client}, ${due:.2f} due on {cdate}, {pcount} existing payments")
        print()

# Export detailed backup for manual review
export_file = f"l:\\limo\\data\\orphaned_payments_backup_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
print(f"\nExporting detailed backup to {export_file}...")

with open(export_file, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['payment_id', 'original_reserve_number', 'amount', 'payment_date', 'payment_method', 'payment_key', 'exists_in_charters'])
    
    for pid, rn, amt, pdate, method, pkey in orphaned:
        exists = rn in existing_reserves
        writer.writerow([pid, rn, amt, pdate, method, pkey, 'YES' if exists else 'NO'])

print(f"✅ Exported {len(orphaned)} payments to backup analysis file\n")

cur.close()
conn.close()
