#!/usr/bin/env python3
"""
Research vague vendor names to determine actual vendors.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("RESEARCHING VAGUE VENDOR NAMES")
print("=" * 80)

# List of vague vendors to research
vague_vendors = [
    'CUSTOMER DEPOSIT',
    'BANK FEE',
    'BANKING TRANSACTION',
    'BRANCH TRANSACTION',
    'DEPOSIT (UNSPECIFIED)',
    'BUSINESS EXPENSE (CIBC AUTO-GEN)',
]

for vendor in vague_vendors:
    print(f"\n{'='*80}")
    print(f"VENDOR: {vendor}")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.gross_amount,
            r.description as receipt_desc,
            b.description as banking_desc,
            b.vendor_extracted as banking_vendor,
            b.debit_amount,
            b.credit_amount
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
        LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
        WHERE r.vendor_name = %s
        ORDER BY r.gross_amount DESC
        LIMIT 10
    """, (vendor,))
    
    results = cur.fetchall()
    
    if not results:
        print("  Not found in database")
        continue
    
    print(f"\nFound {len(results)} receipts (showing top 10):\n")
    
    for r_id, r_date, r_amt, r_desc, b_desc, b_vendor, b_debit, b_credit in results:
        amt_str = f"${r_amt:.2f}" if r_amt else "$0.00"
        print(f"Date: {r_date} | Amount: {amt_str}")
        if r_desc:
            print(f"  Receipt desc: {r_desc[:70]}")
        if b_desc:
            print(f"  Banking desc: {b_desc[:70]}")
        if b_vendor:
            print(f"  Banking vendor: {b_vendor}")
        print()

# Also check for vendors that might be COOP
print("\n" + "=" * 80)
print("CHECKING FOR COOP/CAPS VARIATIONS")
print("=" * 80)

cur.execute("""
    SELECT DISTINCT vendor_name
    FROM receipts
    WHERE vendor_name LIKE '%COOP%'
       OR vendor_name LIKE '%CAPS%'
       OR vendor_name LIKE '%CO-OP%'
       OR vendor_name LIKE '%C.O.P%'
    ORDER BY vendor_name
""")

coop_vendors = cur.fetchall()
print(f"\nFound {len(coop_vendors)} COOP/CAPS related vendors:")
for (vendor,) in coop_vendors:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name = %s
    """, (vendor,))
    count, total = cur.fetchone()
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"  {vendor:40} {count:4} receipts  {total_str}")

# Check for generic "POINT OF" vendor
print("\n" + "=" * 80)
print("CHECKING POINT OF VENDOR")
print("=" * 80)

cur.execute("""
    SELECT 
        r.receipt_date,
        r.gross_amount,
        r.description,
        b.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'POINT OF'
    ORDER BY r.gross_amount DESC
    LIMIT 20
""")

point_of = cur.fetchall()
if point_of:
    print(f"\nFound {len(point_of)} 'POINT OF' receipts (showing top 20):\n")
    for r_date, r_amt, r_desc, b_desc in point_of:
        amt_str = f"${r_amt:.2f}" if r_amt else "$0.00"
        print(f"{r_date} | {amt_str:>10}")
        if b_desc:
            print(f"  Banking: {b_desc[:70]}")
        if r_desc:
            print(f"  Receipt: {r_desc[:70]}")
        print()

# Check other vague single-word vendors
print("\n" + "=" * 80)
print("CHECKING OTHER VAGUE VENDORS")
print("=" * 80)

cur.execute("""
    SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
    FROM receipts
    WHERE LENGTH(vendor_name) <= 15
      AND vendor_name NOT LIKE '%-%'
      AND vendor_name NOT LIKE '% %'
      AND vendor_name != 'NSF CHARGE'
      AND vendor_name != 'EMAIL TRANSFER'
    GROUP BY vendor_name
    HAVING COUNT(*) > 5
    ORDER BY count DESC
    LIMIT 30
""")

short_vendors = cur.fetchall()
print(f"\nShort/vague vendor names (>5 receipts):")
for vendor, count, total in short_vendors:
    total_str = f"${total:,.2f}" if total else "$0.00"
    print(f"  {vendor:30} {count:4} receipts  {total_str}")

cur.close()
conn.close()

print("\n✅ COMPLETE")
