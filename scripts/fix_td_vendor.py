#!/usr/bin/env python3
"""
Look up TD banking descriptions and apply proper fix.
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
print("RESEARCHING TD VENDOR")
print("=" * 80)

# Get all TD receipts with banking matches
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
    WHERE r.vendor_name = 'TD (BANK OR INSURANCE)'
    ORDER BY r.gross_amount DESC
""")

results = cur.fetchall()

print(f"\nFound {len(results)} TD receipts\n")

for r_id, r_date, r_amt, r_desc, b_desc, b_vendor, b_debit, b_credit in results:
    print(f"Date: {r_date} | Amount: ${r_amt:.2f}")
    if r_desc:
        print(f"  Receipt: {r_desc[:70]}")
    if b_desc:
        print(f"  Banking: {b_desc[:70]}")
    if b_vendor:
        print(f"  Vendor: {b_vendor}")
    print()

# Based on receipt descriptions, most are insurance
# Update to proper name
print("=" * 80)
print("APPLYING FIX")
print("=" * 80)

cur.execute("""
    UPDATE receipts
    SET vendor_name = 'TD INSURANCE'
    WHERE vendor_name = 'TD (BANK OR INSURANCE)'
      AND (description LIKE '%Insurance%' 
           OR description LIKE '%Policy%'
           OR description LIKE '%Fleet%')
""")

insurance_count = cur.rowcount
print(f"✅ Updated {insurance_count} receipts to TD INSURANCE")

# Update remaining to TD (UNKNOWN)
cur.execute("""
    UPDATE receipts
    SET vendor_name = 'TD (UNKNOWN TYPE)'
    WHERE vendor_name = 'TD (BANK OR INSURANCE)'
""")

unknown_count = cur.rowcount
print(f"✅ Updated {unknown_count} receipts to TD (UNKNOWN TYPE)")

conn.commit()

# Now check for other vendors that might have been renamed
print("\n\n" + "=" * 80)
print("CHECKING RECENTLY CHANGED VENDORS")
print("=" * 80)

recently_changed = [
    'FIRST INSURANCE FUNDING',
    'ERLES AUTO REPAIR',
    'THE LIQUOR HUTCH',
    'LEASE FINANCE GROUP',
    'CHECK PAYMENT',
]

for vendor in recently_changed:
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name = %s
    """, (vendor,))
    
    count, total = cur.fetchone()
    if count and count > 0:
        total_str = f"${total:,.2f}" if total else "$0.00"
        print(f"  {vendor:40} {count:4} receipts  {total_str}")

cur.close()
conn.close()

print("\n✅ COMPLETE")
