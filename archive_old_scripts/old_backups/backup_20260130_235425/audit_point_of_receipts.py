#!/usr/bin/env python3
"""
Audit remaining 239 POINT OF receipts.
Check if they match banking or are cash/QuickBooks entries.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("=" * 80)
print("AUDITING REMAINING 239 POINT OF RECEIPTS")
print("=" * 80)

# Check banking match status
cur.execute("""
    SELECT 
        CASE 
            WHEN brml.receipt_id IS NOT NULL THEN 'HAS_BANKING_MATCH'
            ELSE 'NO_BANKING_MATCH'
        END as status,
        COUNT(*) as count,
        SUM(r.gross_amount) as total
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    WHERE r.vendor_name = 'POINT OF'
    GROUP BY status
""")

print("\n1. BANKING MATCH STATUS:")
for status, count, total in cur.fetchall():
    print(f"  {status:20} {count:>6,} receipts  ${total:>12,.2f}")

# Check payment methods
cur.execute("""
    SELECT 
        COALESCE(payment_method, 'NULL') as payment,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name = 'POINT OF'
    GROUP BY payment_method
    ORDER BY count DESC
""")

print("\n2. PAYMENT METHODS:")
for payment, count, total in cur.fetchall():
    print(f"  {payment:20} {count:>6,} receipts  ${total:>12,.2f}")

# Check categories
cur.execute("""
    SELECT 
        COALESCE(category, 'NULL') as cat,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name = 'POINT OF'
    GROUP BY category
    ORDER BY count DESC
""")

print("\n3. CATEGORIES:")
for cat, count, total in cur.fetchall():
    print(f"  {cat:30} {count:>6,} receipts  ${total:>12,.2f}")

# Check receipts WITH banking but still POINT OF
print("\n\n4. POINT OF RECEIPTS WITH BANKING MATCH (should have vendor extracted):")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.description as receipt_desc,
        r.payment_method,
        bt.description as banking_desc
    FROM receipts r
    JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'POINT OF'
    ORDER BY r.gross_amount DESC
    LIMIT 20
""")

with_banking = cur.fetchall()
print(f"Found {len(with_banking)} POINT OF receipts WITH banking match:")
for receipt_id, date, amount, receipt_desc, payment, banking_desc in with_banking:
    print(f"\n  Receipt {receipt_id} | {date} | ${amount:,.2f} | Payment: {payment}")
    print(f"    Receipt desc: {receipt_desc}")
    print(f"    Banking desc: {banking_desc[:100]}")

# Check receipts WITHOUT banking (manual entries)
print("\n\n5. POINT OF RECEIPTS WITHOUT BANKING MATCH (manual/cash/QuickBooks):")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.description,
        r.payment_method,
        r.category,
        r.created_from_banking
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    WHERE r.vendor_name = 'POINT OF'
      AND brml.receipt_id IS NULL
    ORDER BY r.gross_amount DESC
    LIMIT 20
""")

without_banking = cur.fetchall()
print(f"Found {len(without_banking)} POINT OF receipts WITHOUT banking match:")
for receipt_id, date, amount, desc, payment, category, from_banking in without_banking:
    source = "AUTO-BANKING" if from_banking else "MANUAL/QB"
    payment_str = payment if payment else "None"
    category_str = category if category else "None"
    print(f"  {receipt_id} | {date} | ${amount:>8,.2f} | {payment_str:15} | {category_str:20} | {source}")
    if desc:
        print(f"    Desc: {desc[:80]}")

# Summary
print("\n\n" + "=" * 80)
print("AUDIT SUMMARY")
print("=" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(brml.receipt_id) as with_banking,
        COUNT(*) - COUNT(brml.receipt_id) as without_banking,
        SUM(r.gross_amount) as total_amount
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    WHERE r.vendor_name = 'POINT OF'
""")

total, with_banking, without_banking, total_amt = cur.fetchone()

print(f"\nTotal POINT OF receipts: {total:,} (${total_amt:,.2f})")
print(f"  With banking match: {with_banking:,} ({100*with_banking/total:.1f}%)")
print(f"  Without banking match: {without_banking:,} ({100*without_banking/total:.1f}%)")

if with_banking > 0:
    print(f"\n⚠️  WARNING: {with_banking} POINT OF receipts HAVE banking matches")
    print("   These should have had vendor names extracted from banking!")
    print("   This indicates extraction failed for these records.")

if without_banking > 0:
    print(f"\n✅ {without_banking} POINT OF receipts are manual/cash entries (NO banking)")
    print("   These are legitimate - they're from QuickBooks or manual entry.")

cur.close()
conn.close()
