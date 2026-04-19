#!/usr/bin/env python3
"""
Build a priority queue for expense intake:
1) Unlinked banking debits (missing receipts)
2) Receipts without vendor invoice link
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

print('=== Missing Receipt Intake: Top debit descriptions (unlinked banking debits) ===')
cur.execute("""
SELECT
    COALESCE(NULLIF(TRIM(description), ''), '[NO DESCRIPTION]') AS descr,
    COUNT(*) AS tx_count,
    COALESCE(SUM(debit_amount),0) AS total
FROM banking_transactions
WHERE debit_amount > 0
  AND receipt_id IS NULL
GROUP BY COALESCE(NULLIF(TRIM(description), ''), '[NO DESCRIPTION]')
ORDER BY total DESC
LIMIT 25
""")
for d, c, t in cur.fetchall():
    print(f"{t:12,.2f} | {c:5} | {d[:90]}")

print('\n=== Receipts without invoice link: Top vendors ===')
cur.execute("""
SELECT
    COALESCE(NULLIF(TRIM(vendor_name), ''), '[NO VENDOR]') AS vendor,
    COUNT(*) AS receipt_count,
    COALESCE(SUM(gross_amount),0) AS total
FROM receipts r
WHERE NOT EXISTS (
    SELECT 1 FROM vendor_invoices v WHERE v.source_receipt_id = r.receipt_id
)
GROUP BY COALESCE(NULLIF(TRIM(vendor_name), ''), '[NO VENDOR]')
ORDER BY total DESC
LIMIT 25
""")
for v, c, t in cur.fetchall():
    print(f"{t:12,.2f} | {c:5} | {v[:90]}")

cur.close()
conn.close()
