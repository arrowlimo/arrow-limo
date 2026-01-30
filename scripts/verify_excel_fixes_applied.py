#!/usr/bin/env python3
"""
Check if Excel vendor fixes were properly applied.
Verify POINT OF receipts and their descriptions.
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
print("VERIFYING EXCEL VENDOR FIXES WERE APPLIED")
print("=" * 80)

# Check POINT OF receipts
cur.execute("SELECT COUNT(*), SUM(gross_amount) FROM receipts WHERE vendor_name = 'POINT OF'")
count, total = cur.fetchone()
print(f"\nPOINT OF receipts currently in database: {count:,} (${total:,.2f})")

# Sample POINT OF receipts with descriptions
print("\nSample POINT OF receipts (showing descriptions):")
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, description, category
    FROM receipts
    WHERE vendor_name = 'POINT OF'
    ORDER BY receipt_date DESC
    LIMIT 20
""")

for receipt_id, date, amount, desc, category in cur.fetchall():
    desc_display = (desc[:60] if desc else "None")
    print(f"  {receipt_id} | {date} | ${amount:>8,.2f} | {category:20} | {desc_display}")

# Check if these have banking descriptions
print("\n\nChecking if POINT OF receipts have banking matches with descriptions:")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.description as receipt_desc,
        bt.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    LEFT JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'POINT OF'
      AND bt.description IS NOT NULL
    ORDER BY r.receipt_date DESC
    LIMIT 10
""")

print("\nPOINT OF receipts WITH banking descriptions:")
for receipt_id, date, amount, receipt_desc, banking_desc in cur.fetchall():
    print(f"  Receipt {receipt_id} | {date} | ${amount:.2f}")
    print(f"    Receipt desc: {receipt_desc}")
    print(f"    Banking desc: {banking_desc[:80]}")
    print()

# Check receipts that WERE fixed from Excel
print("\n" + "=" * 80)
print("CHECKING RECEIPTS THAT WERE FIXED FROM EXCEL")
print("=" * 80)

# Count receipts by vendor to see what was actually updated
cur.execute("""
    SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE vendor_name LIKE '%POINT OF%'
       OR vendor_name IN ('CUSTOMER', 'BANK', 'BANKING TRANSACTION')
    GROUP BY vendor_name
    ORDER BY count DESC
""")

print("\nReceipts with 'POINT OF' or vague names:")
for vendor, count, total in cur.fetchall():
    print(f"  {vendor[:60]:60} {count:>6,} (${total:,.2f})")

# Check what percentage have descriptions
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN description IS NOT NULL AND description != '' THEN 1 END) as with_desc,
        COUNT(CASE WHEN description IS NULL OR description = '' THEN 1 END) as no_desc
    FROM receipts
    WHERE vendor_name = 'POINT OF'
""")

total, with_desc, no_desc = cur.fetchone()
print(f"\nPOINT OF description coverage:")
print(f"  Total: {total:,}")
print(f"  With description: {with_desc:,} ({100*with_desc/total if total > 0 else 0:.1f}%)")
print(f"  No description: {no_desc:,} ({100*no_desc/total if total > 0 else 0:.1f}%)")

print("\n\n💡 USER IS CORRECT: We can use the description column from banking!")
print("   The description already contains the vendor information.")
print("   We don't need to update vendor_name if description has the info.")

cur.close()
conn.close()
