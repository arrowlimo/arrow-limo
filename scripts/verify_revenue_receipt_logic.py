#!/usr/bin/env python3
"""Verify revenue receipts are being created correctly and identify gaps."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("REVENUE RECEIPTS - VERIFICATION")
print("=" * 80)

# 1. Check receipts with revenue column populated
print("\n1️⃣  RECEIPTS WITH REVENUE COLUMN POPULATED")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as count,
        SUM(revenue) as total_revenue,
        SUM(gross_amount) as total_gross,
        MIN(receipt_date) as earliest,
        MAX(receipt_date) as latest
    FROM receipts
    WHERE revenue > 0
""")

count, total_rev, total_gross, earliest, latest = cur.fetchone()
print(f"✓ {count:,} receipts with revenue column")
print(f"  Total revenue: ${total_rev:,.2f}")
print(f"  Total gross: ${total_gross:,.2f}")
print(f"  Date range: {earliest} to {latest}")

# 2. Check if revenue receipts have GL codes and GST exempt
print("\n2️⃣  REVENUE RECEIPTS - GL & GST STATUS")
print("-" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN gl_account_code IS NOT NULL THEN 'Has GL Code'
            ELSE 'Missing GL Code'
        END as gl_status,
        CASE 
            WHEN gst_exempt = true THEN 'GST Exempt'
            ELSE 'Not Exempt'
        END as gst_status,
        COUNT(*) as count,
        SUM(revenue) as total_revenue
    FROM receipts
    WHERE revenue > 0
    GROUP BY gl_status, gst_status
    ORDER BY gl_status, gst_status
""")

for gl_status, gst_status, count, revenue in cur.fetchall():
    print(f"  {gl_status:20s} | {gst_status:12s} | {count:6,d} receipts | ${revenue:12,.2f}")

# 3. Check which credit transactions have revenue receipts
print("\n3️⃣  CREDIT TRANSACTIONS (Money In) - RECEIPT STATUS")
print("-" * 80)

cur.execute("""
    SELECT 
        bt.account_number,
        COUNT(*) as total_credits,
        COUNT(r.receipt_id) FILTER (WHERE r.revenue > 0) as has_revenue_receipt,
        COUNT(r.receipt_id) FILTER (WHERE r.revenue IS NULL OR r.revenue = 0) as has_other_receipt,
        COUNT(*) FILTER (WHERE r.receipt_id IS NULL) as no_receipt,
        SUM(bt.credit_amount) as total_amount
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0
    GROUP BY bt.account_number
    ORDER BY bt.account_number
""")

print("\nAccount         | Total Credits | Revenue Receipt | Other Receipt | No Receipt | Total Amount")
print("-" * 100)
for account, total, has_rev, has_other, no_receipt, amount in cur.fetchall():
    print(f"{account:15s} | {total:13,d} | {has_rev:15,d} | {has_other:13,d} | {no_receipt:10,d} | ${amount:12,.2f}")

# 4. Sample revenue receipts
print("\n4️⃣  SAMPLE REVENUE RECEIPTS (Latest 10)")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_date,
        r.vendor_name,
        r.revenue,
        r.gross_amount,
        r.gl_account_code,
        r.gst_exempt,
        r.description
    FROM receipts r
    WHERE r.revenue > 0
    ORDER BY r.receipt_date DESC
    LIMIT 10
""")

for date, vendor, revenue, gross, gl_code, gst_exempt, desc in cur.fetchall():
    exempt_text = "EXEMPT" if gst_exempt else "Taxable"
    gl_text = gl_code or "NO GL"
    print(f"{date} | {vendor:25s} | ${revenue:10.2f} | {gl_text:15s} | {exempt_text:7s} | {desc[:30] if desc else ''}")

# 5. Identify which credit transactions need revenue receipts created
print("\n5️⃣  CREDIT TRANSACTIONS NEEDING REVENUE RECEIPTS")
print("-" * 80)

cur.execute("""
    SELECT 
        bt.account_number,
        COUNT(*) as missing_count,
        SUM(bt.credit_amount) as total_amount
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0
      AND r.receipt_id IS NULL
    GROUP BY bt.account_number
    ORDER BY bt.account_number
""")

results = cur.fetchall()
total_missing = sum(r[1] for r in results)
total_amount = sum(r[2] for r in results)

print(f"\n⚠️  {total_missing:,} credit transactions WITHOUT any receipt:")
for account, count, amount in results:
    print(f"   {account:15s}: {count:6,d} transactions | ${amount:12,.2f}")

print(f"\n   TOTAL MISSING: {total_missing:,} transactions | ${total_amount:,.2f}")

print("\n" + "=" * 80)

cur.close()
conn.close()
