#!/usr/bin/env python3
"""
Step 1: Delete obvious orphaned payments (18-19 year gaps on pre-2020 charters).
Then export the payment details to find their true source.
"""

import psycopg2
import os
import csv
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("STEP 1: DELETE OBVIOUS ORPHANED PAYMENTS")
print("=" * 100)

# Get the 106 orphaned payments for export BEFORE deletion
print("\n1. EXPORTING ORPHANED PAYMENT DETAILS (for source tracing):")
cur.execute("""
SELECT 
    p.payment_id,
    p.reserve_number,
    p.payment_date,
    p.amount,
    p.payment_method,
    p.notes,
    p.banking_transaction_id,
    p.square_transaction_id,
    p.status,
    c.charter_date,
    c.status as charter_status
FROM payments p
JOIN charters c ON c.reserve_number = p.reserve_number
WHERE p.payment_date >= '2025-01-01'
  AND c.charter_date < '2020-01-01'
ORDER BY p.reserve_number, p.payment_date
""")
orphaned = cur.fetchall()

# Export to CSV for manual review
export_file = f"l:\\limo\\data\\orphaned_payments_for_remapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
with open(export_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['payment_id', 'reserve_number', 'payment_date', 'amount', 'payment_method', 'notes', 'banking_transaction_id', 'square_transaction_id', 'payment_status', 'charter_date', 'charter_status'])
    for row in orphaned:
        writer.writerow(row)

print(f"   Exported {len(orphaned)} orphaned payments to:")
print(f"   {export_file}")

# Analyze source patterns
print("\n2. ORPHANED PAYMENT SOURCE ANALYSIS:")
cur.execute("""
SELECT 
    CASE 
        WHEN banking_transaction_id IS NOT NULL THEN 'Banking-linked'
        WHEN square_transaction_id IS NOT NULL THEN 'Square payment'
        WHEN payment_method = 'unknown' THEN 'Unknown method'
        ELSE payment_method
    END as source_type,
    COUNT(*) as count,
    SUM(amount) as total
FROM payments
WHERE payment_date >= '2025-01-01'
  AND reserve_number IN (
    SELECT DISTINCT c.reserve_number
    FROM charters c
    WHERE c.charter_date < '2020-01-01'
  )
GROUP BY source_type
""")
rows = cur.fetchall()
for source, count, total in rows:
    print(f"   {source:25} {count:3} payments, ${total:10,.2f}")

# Ask before deletion
print("\n" + "=" * 100)
print("READY TO DELETE?")
print(f"   • {len(orphaned)} obvious orphaned payments")
print(f"   • Total amount: ${sum(p[3] for p in orphaned):,.2f}")
print(f"   • All from 2025-01-01 onwards on pre-2020 charters (18-19 year gaps)")
print("\nUsage: python delete_orphaned_payments.py --delete-confirmed")
print("=" * 100)

cur.close()
conn.close()
