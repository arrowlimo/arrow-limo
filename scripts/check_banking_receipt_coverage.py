#!/usr/bin/env python3
"""Check if all banking transactions have receipts with proper GL and GST handling."""

import psycopg2
from decimal import Decimal

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("BANKING TRANSACTION → RECEIPT COVERAGE ANALYSIS")
print("=" * 80)

# 1. Check banking transactions without receipts
print("\n1️⃣  BANKING TRANSACTIONS WITHOUT RECEIPTS")
print("-" * 80)

cur.execute("""
    SELECT 
        bt.account_number,
        COUNT(*) as unmatched_count,
        SUM(COALESCE(bt.debit_amount, bt.credit_amount)) as total_amount
    FROM banking_transactions bt
    WHERE bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id 
        FROM receipts 
        WHERE banking_transaction_id IS NOT NULL
    )
    AND bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id
        FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id IS NOT NULL
    )
    GROUP BY bt.account_number
    ORDER BY bt.account_number
""")

unmatched = cur.fetchall()
if unmatched:
    print("\n⚠️  Banking transactions WITHOUT receipts:")
    for account, count, amount in unmatched:
        print(f"   Account {account}: {count:,} transactions, ${amount:,.2f}")
else:
    print("✓ All banking transactions have receipts!")

# 2. Check receipts with GL accounts
print("\n\n2️⃣  RECEIPT GL ACCOUNT ASSIGNMENT")
print("-" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN gl_account_code IS NOT NULL THEN 'Has GL Account'
            ELSE 'Missing GL Account'
        END as gl_status,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE created_from_banking = true
    GROUP BY gl_status
    ORDER BY gl_status
""")

gl_results = cur.fetchall()
for status, count, amount in gl_results:
    icon = "✓" if "Has" in status else "⚠️"
    print(f"{icon} {status}: {count:,} receipts, ${amount:,.2f}")

# 3. Check GST handling on receipts
print("\n\n3️⃣  GST HANDLING ON RECEIPTS")
print("-" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN gst_exempt = true THEN 'GST Exempt'
            WHEN gst_amount > 0 THEN 'GST Calculated'
            WHEN gst_amount = 0 AND gst_exempt = false THEN 'GST Zero (not exempt)'
            ELSE 'Unknown'
        END as gst_status,
        COUNT(*) as receipt_count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE created_from_banking = true
    GROUP BY gst_status
    ORDER BY gst_status
""")

gst_results = cur.fetchall()
for status, count, amount in gst_results:
    print(f"   {status}: {count:,} receipts, ${amount:,.2f}")

# 4. Sample receipts created from banking
print("\n\n4️⃣  SAMPLE BANKING-CREATED RECEIPTS (Latest 10)")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.gst_amount,
        r.gst_exempt,
        r.gl_account_name
    FROM receipts r
    WHERE r.created_from_banking = true
    ORDER BY r.receipt_date DESC
    LIMIT 10
""")

samples = cur.fetchall()
if samples:
    for receipt_id, date, vendor, gross, gst, exempt, gl_name in samples:
        gst_status = "EXEMPT" if exempt else f"GST ${gst:.2f}"
        gl_display = gl_name if gl_name else "NO GL ACCOUNT"
        print(f"   {date} | {vendor[:30]:30s} | ${gross:8.2f} | {gst_status:12s} | {gl_display}")

# 5. Check for receipts missing GL accounts (detailed)
print("\n\n5️⃣  RECEIPTS MISSING GL ACCOUNTS (Sample)")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.created_from_banking
    FROM receipts r
    WHERE r.gl_account_code IS NULL
      AND r.created_from_banking = true
    ORDER BY r.receipt_date DESC
    LIMIT 10
""")

missing_gl = cur.fetchall()
if missing_gl:
    print("\n⚠️  Sample receipts without GL accounts:")
    for receipt_id, date, vendor, gross, from_banking in missing_gl:
        print(f"   ID {receipt_id} | {date} | {vendor[:40]:40s} | ${gross:8.2f}")
else:
    print("✓ All banking-created receipts have GL accounts!")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)

cur.close()
conn.close()
