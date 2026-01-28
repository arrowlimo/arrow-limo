#!/usr/bin/env python3
"""
Audit LMS (Legacy Management System) errors and sync issues.
Checks for:
1. Charter notes with LMS sync markers
2. Mismatched data between LMS and almsdata
3. Failed sync records
4. Data inconsistencies
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("LMS ERROR AUDIT REPORT")
print("=" * 80)

# 1. Charter notes with LMS sync markers
print("\n1. CHARTERS WITH LMS SYNC MARKERS IN NOTES:")
cur.execute("""
SELECT COUNT(*) as count, 
       SUM(CASE WHEN notes ILIKE '%LMS Sync%' THEN 1 ELSE 0 END) as lms_sync_count,
       SUM(CASE WHEN notes ILIKE '%LMS%error%' OR notes ILIKE '%error%LMS%' THEN 1 ELSE 0 END) as lms_error_count
FROM charters
WHERE notes IS NOT NULL
""")
result = cur.fetchone()
print(f"   Total charters with notes: {result[0]}")
print(f"   With [LMS Sync ...] marker: {result[1] or 0}")
print(f"   With LMS error mention: {result[2] or 0}")

# 2. Detailed LMS sync entries
print("\n2. RECENT LMS SYNC MARKERS (last 20):")
cur.execute("""
SELECT charter_id, reserve_number, charter_date, 
       substring(notes from '\\[LMS Sync[^\\]]*\\]') as sync_marker
FROM charters
WHERE notes ILIKE '%LMS Sync%'
ORDER BY charter_id DESC
LIMIT 20
""")
rows = cur.fetchall()
for charter_id, reserve, date, marker in rows:
    print(f"   {reserve:6} ({date}) - {marker}")

# 3. Charter-payment mismatches (no payments but has charges)
print("\n3. UNPAID CHARTERS WITH CHARGES (potential LMS sync issues):")
cur.execute("""
SELECT COUNT(*) as unpaid_with_charges,
       SUM(COALESCE(cc.amount, 0)) as total_charges
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE p.reserve_number IS NULL
  AND cc.amount IS NOT NULL AND cc.amount > 0
  AND c.charter_date >= '2025-01-01'
""")
result = cur.fetchone()
print(f"   Post-2025 unpaid charters with charges: {result[0]}")
print(f"   Total amount: ${result[1]:,.2f}")

# 4. Charters with NULL status
print("\n4. CHARTERS WITH NULL OR BLANK STATUS (data quality issue):")
cur.execute("""
SELECT COUNT(*) as null_status_count,
       SUM(COALESCE(cc.amount, 0)) as total_charges
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
WHERE c.status IS NULL OR c.status = ''
""")
result = cur.fetchone()
print(f"   Count: {result[0]}")
if result[0] > 0:
    print(f"   With charges: ${result[1]:,.2f}")

# 5. Duplicate or near-duplicate charters (potential sync errors)
print("\n5. POTENTIAL DUPLICATE CHARTERS (same date/amount/description):")
cur.execute("""
SELECT c1.reserve_number as reserve1, c2.reserve_number as reserve2,
       c1.charter_date, c1.status as status1, c2.status as status2,
       SUM(COALESCE(cc1.amount, 0)) as charges1,
       SUM(COALESCE(cc2.amount, 0)) as charges2
FROM charters c1
JOIN charters c2 ON c1.charter_date = c2.charter_date 
  AND c1.reserve_number < c2.reserve_number
  AND c1.charter_date >= '2024-01-01'
LEFT JOIN charter_charges cc1 ON cc1.charter_id = c1.charter_id
LEFT JOIN charter_charges cc2 ON cc2.charter_id = c2.charter_id
WHERE COALESCE(SUM(COALESCE(cc1.amount, 0)), 0) = COALESCE(SUM(COALESCE(cc2.amount, 0)), 0)
  AND COALESCE(SUM(COALESCE(cc1.amount, 0)), 0) > 0
GROUP BY c1.charter_id, c2.charter_id, c1.reserve_number, c2.reserve_number,
         c1.charter_date, c1.status, c2.status
LIMIT 10
""")
rows = cur.fetchall()
if rows:
    for res1, res2, date, status1, status2, charges1, charges2 in rows:
        print(f"   {res1} ({status1}) ←→ {res2} ({status2}) on {date}: ${charges1:,.2f}")
else:
    print("   None found (good)")

# 6. Payments without matching charters (orphaned)
print("\n6. ORPHANED PAYMENTS (no matching charter):")
cur.execute("""
SELECT COUNT(*) as orphaned_count,
       SUM(amount) as total_orphaned
FROM payments p
WHERE p.reserve_number IS NULL
   OR NOT EXISTS (SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number)
""")
result = cur.fetchone()
print(f"   Count: {result[0]}")
print(f"   Total amount: ${result[1]:,.2f}")

# 7. Receipts matching issues
print("\n7. RECEIPTS WITH MATCHING ISSUES:")
cur.execute("""
SELECT COUNT(*) as receipts_no_charter,
       SUM(amount) as total_amount
FROM receipts r
WHERE charter_matched_id IS NULL 
  AND receipt_date >= '2024-01-01'
  AND (vendor_name ILIKE '%charter%' OR notes ILIKE '%charter%')
""")
result = cur.fetchone()
print(f"   Receipts mentioning 'charter' but not matched: {result[0]}")
print(f"   Total amount: ${result[1]:,.2f}")

# 8. Banking transaction sync issues
print("\n8. BANKING TRANSACTION SYNC ISSUES:")
cur.execute("""
SELECT COUNT(*) as unmatched_banking,
       SUM(amount) as total_unmatched
FROM banking_transactions bt
WHERE bt.matched_receipt_id IS NULL
  AND transaction_date >= '2025-01-01'
""")
result = cur.fetchone()
print(f"   Unmatched banking transactions (2025+): {result[0]}")
print(f"   Total amount: ${result[1]:,.2f}")

# 9. Data integrity checks
print("\n9. DATA INTEGRITY CHECKS:")
cur.execute("""
SELECT 'Charters with zero/null amount_due' as check_name,
       COUNT(*) as count,
       SUM(COALESCE(amount_due, 0)) as total
FROM charters
WHERE amount_due IS NULL OR amount_due = 0
UNION ALL
SELECT 'Payments with negative amount',
       COUNT(*),
       SUM(amount)
FROM payments
WHERE amount < 0
UNION ALL
SELECT 'Receipts with conflicting revenue/expense',
       COUNT(*),
       SUM(CASE WHEN revenue > 0 AND expense > 0 THEN 1 ELSE 0 END)
FROM receipts
WHERE revenue > 0 AND expense > 0
""")
rows = cur.fetchall()
for check_name, count, total in rows:
    print(f"   {check_name}: {count} records")

print("\n" + "=" * 80)
cur.close()
conn.close()
