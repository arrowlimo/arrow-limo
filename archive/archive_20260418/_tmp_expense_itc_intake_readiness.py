#!/usr/bin/env python3
"""
Expense-side readiness snapshot for ITC + invoicing + missing receipt intake.
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

print('=== Revenue Ledger Confirmation ===')
cur.execute("""
SELECT COUNT(*), COALESCE(SUM(gross_amount),0)
FROM income_ledger
WHERE source_system='charter_payments'
""")
print('income_ledger from charter_payments:', cur.fetchone())

print('\n=== Expense ITC Baseline (receipts) ===')
cur.execute("""
SELECT
    COUNT(*) AS receipts_count,
    COALESCE(SUM(gross_amount),0) AS gross_total,
    COALESCE(SUM(gst_amount),0) AS gst_total,
    COUNT(*) FILTER (WHERE COALESCE(gst_amount,0) > 0) AS gst_positive_count,
    COUNT(*) FILTER (WHERE COALESCE(gst_amount,0) = 0) AS gst_zero_count
FROM receipts
""")
print('receipts summary:', cur.fetchone())

print('\n=== Unlinked Banking Debits (missing receipt intake pool) ===')
cur.execute("""
SELECT
    COUNT(*) AS unlinked_debits,
    COALESCE(SUM(debit_amount),0) AS debit_total
FROM banking_transactions
WHERE debit_amount > 0
  AND receipt_id IS NULL
""")
print('unlinked debit pool:', cur.fetchone())

print('\n=== Receipts Missing Invoice Link ===')
cur.execute("""
SELECT
    COUNT(*) AS no_invoice_link
FROM receipts r
WHERE NOT EXISTS (
    SELECT 1
    FROM vendor_invoices v
    WHERE v.source_receipt_id = r.receipt_id
)
""")
print('receipts without vendor_invoice link:', cur.fetchone()[0])

print('\n=== ITC-ready Receipts (simple rule: gst_amount > 0 and non-personal flags absent) ===')
cur.execute("""
SELECT column_name
FROM information_schema.columns
WHERE table_name='receipts'
ORDER BY column_name
""")
cols = {r[0] for r in cur.fetchall()}

has_personal = 'is_personal_purchase' in cols
has_owner_personal_amount = 'owner_personal_amount' in cols
has_exclude = 'exclude_from_reports' in cols

where_parts = ["COALESCE(gst_amount,0) > 0"]
if has_personal:
    where_parts.append("COALESCE(is_personal_purchase,false)=false")
if has_owner_personal_amount:
    where_parts.append("COALESCE(owner_personal_amount,0)=0")
if has_exclude:
    where_parts.append("COALESCE(exclude_from_reports,false)=false")

where_sql = ' AND '.join(where_parts)

cur.execute(f"""
SELECT
    COUNT(*) AS itc_candidate_count,
    COALESCE(SUM(gst_amount),0) AS itc_candidate_gst
FROM receipts
WHERE {where_sql}
""")
print('itc candidate summary:', cur.fetchone())

cur.close()
conn.close()
