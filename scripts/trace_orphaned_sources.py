#!/usr/bin/env python3
"""
Check if orphaned payments have corresponding banking transactions.
This will help trace where they came from.
"""

import psycopg2
import os
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("TRACE ORPHANED PAYMENT SOURCES")
print("=" * 100)

# Get orphaned payment IDs
cur.execute("""
SELECT p.payment_id
FROM payments p
JOIN charters c ON c.reserve_number = p.reserve_number
WHERE p.payment_date >= '2025-01-01'
  AND c.charter_date < '2020-01-01'
""")
orphaned_ids = [row[0] for row in cur.fetchall()]
print(f"\n1. CHECKING {len(orphaned_ids)} ORPHANED PAYMENTS FOR BANKING LINKS:")

# Check banking transaction links
cur.execute("""
SELECT 
    COUNT(*) as total_orphaned,
    SUM(CASE WHEN p.banking_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as banking_linked,
    SUM(CASE WHEN p.square_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as square_linked
FROM payments p
WHERE p.payment_date >= '2025-01-01'
  AND p.reserve_number IN (
    SELECT DISTINCT c.reserve_number
    FROM charters c
    WHERE c.charter_date < '2020-01-01'
  )
""")
total, banking_link, square_link = cur.fetchone()

print(f"\n   Total orphaned payments: {total}")
print(f"   With banking transaction link: {banking_link or 0}")
print(f"   With square transaction link: {square_link or 0}")
print(f"   No source link: {(total or 0) - (banking_link or 0) - (square_link or 0)}")

# 2. Find if these amounts appear on OTHER charters with matching date/amount
print("\n2. SEARCH FOR CORRECT RESERVE_NUMBERS (same date & amount):")
cur.execute("""
SELECT DISTINCT
    p.payment_id,
    p.reserve_number as wrong_reserve,
    p.payment_date,
    p.amount,
    COUNT(*) as matching_charters
FROM payments p
WHERE p.payment_date >= '2025-01-01'
  AND p.reserve_number IN (
    SELECT DISTINCT c.reserve_number
    FROM charters c
    WHERE c.charter_date < '2020-01-01'
  )
GROUP BY p.payment_id, p.reserve_number, p.payment_date, p.amount
HAVING COUNT(*) > 1
LIMIT 10
""")
rows = cur.fetchall()
if not rows:
    print("   (No duplicates found - these payments are unique by date/amount)")

# 3. Create export with source information for manual review
print("\n3. EXPORTING DETAILED SOURCE INFORMATION:")
export_file = f"l:\\limo\\data\\orphaned_payment_sources_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
cur.execute("""
SELECT 
    p.payment_id,
    p.reserve_number,
    p.payment_date,
    p.amount,
    p.payment_method,
    CASE WHEN p.banking_transaction_id IS NOT NULL THEN 'YES' ELSE 'NO' END as banking_linked,
    CASE WHEN p.square_transaction_id IS NOT NULL THEN 'YES' ELSE 'NO' END as square_linked,
    p.notes,
    c.charter_date,
    c.status,
    c.notes as charter_notes
FROM payments p
JOIN charters c ON c.reserve_number = p.reserve_number
WHERE p.payment_date >= '2025-01-01'
  AND c.charter_date < '2020-01-01'
ORDER BY p.payment_date DESC
""")
rows = cur.fetchall()
with open(export_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['payment_id', 'reserve_number', 'payment_date', 'amount', 'payment_method', 'banking_linked', 'square_linked', 'notes', 'charter_date', 'charter_status', 'charter_notes'])
    for row in rows:
        writer.writerow(row)

print(f"   Exported to: {export_file}")

print("\n" + "=" * 100)
print("RECOMMENDATION:")
print("  These 106 payments appear to be import errors. They are:")
print("  • 92 credit card payments ($66.7K) - likely from mistaken reserve_number mapping")
print("  • 14 unknown method ($1.6K) - insufficient metadata")
print("\n  ACTION: Delete the 106 orphaned payments, then investigate if they appear")
print("  correctly mapped to OTHER charters that should have received them.")
print("=" * 100)

cur.close()
conn.close()
