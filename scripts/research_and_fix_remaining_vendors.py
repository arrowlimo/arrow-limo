#!/usr/bin/env python3
"""
Research and fix remaining vendors (TD, FIRST INSURANCE FUNDING-C, LEASE FINANCE GROUP, etc.)
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
print("RESEARCHING REMAINING VENDORS")
print("=" * 80)

# List of vendors to research
vendors_to_research = [
    'TD',
    'FIRST INSURANCE FUNDING-C',
    'LEASE FINANCE GROUP',
    'CHQ 243',
    'CHQ 244',
    'THE LIQUOR HUTC',
    'ERLES AUTO REPA',
    'FIRST INSURANCE',
]

for vendor in vendors_to_research:
    print(f"\n{'='*80}")
    print(f"VENDOR: {vendor}")
    print("=" * 80)
    
    # Check if vendor exists
    cur.execute("""
        SELECT COUNT(*)
        FROM receipts
        WHERE vendor_name = %s
    """, (vendor,))
    
    count = cur.fetchone()[0]
    print(f"Found {count} receipts")
    
    if count == 0:
        print("  (Not in database - may have been renamed)")
        continue
    
    # Get banking descriptions
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.gross_amount,
            r.description as receipt_desc,
            b.description as banking_desc,
            b.vendor_extracted as banking_vendor
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
        LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
        WHERE r.vendor_name = %s
        ORDER BY r.gross_amount DESC
        LIMIT 10
    """, (vendor,))
    
    results = cur.fetchall()
    
    print("\nOriginal banking descriptions:")
    for r_id, r_date, r_amt, r_desc, b_desc, b_vendor in results:
        print(f"\n  Date: {r_date} | Amount: ${r_amt:.2f}")
        if b_desc:
            print(f"    Banking desc: {b_desc}")
        if b_vendor:
            print(f"    Banking vendor: {b_vendor}")
        if r_desc:
            print(f"    Receipt desc: {r_desc[:70]}")

# Now apply fixes based on findings
print("\n\n" + "=" * 80)
print("APPLYING FIXES")
print("=" * 80)

fixes_to_apply = []

# Check TD
cur.execute("""
    SELECT 
        r.description,
        b.description
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'TD'
    LIMIT 1
""")
td_result = cur.fetchone()
if td_result:
    print(f"\nTD sample: {td_result}")
    # If it's TD Bank, rename to TD BANK
    # If it's TD insurance, rename to TD INSURANCE
    # Default to TD (UNKNOWN TYPE)
    fixes_to_apply.append(('TD', 'TD (BANK OR INSURANCE)'))

# Check FIRST INSURANCE FUNDING-C
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'FIRST INSURANCE FUNDING-C'
""")
if cur.fetchone()[0] > 0:
    fixes_to_apply.append(('FIRST INSURANCE FUNDING-C', 'FIRST INSURANCE FUNDING'))

# Check FIRST INSURANCE (already exists, may need consolidation)
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'FIRST INSURANCE'
""")
if cur.fetchone()[0] > 0:
    fixes_to_apply.append(('FIRST INSURANCE', 'FIRST INSURANCE FUNDING'))

# Check LEASE FINANCE GROUP
cur.execute("""
    SELECT 
        b.description
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'LEASE FINANCE GROUP'
    LIMIT 1
""")
lease_result = cur.fetchone()
if lease_result and lease_result[0]:
    print(f"\nLEASE FINANCE GROUP sample: {lease_result[0]}")
    # Keep as is if it's the full name
    
# Check for THE LIQUOR HUTC (should be HUTCH)
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'THE LIQUOR HUTC'")
if cur.fetchone()[0] > 0:
    fixes_to_apply.append(('THE LIQUOR HUTC', 'THE LIQUOR HUTCH'))

# Check for ERLES AUTO REPA (should be REPAIR)
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'ERLES AUTO REPA'")
if cur.fetchone()[0] > 0:
    fixes_to_apply.append(('ERLES AUTO REPA', 'ERLES AUTO REPAIR'))

# Look for CHQ with numbers
cur.execute("""
    SELECT DISTINCT vendor_name
    FROM receipts
    WHERE vendor_name LIKE 'CHQ %'
    ORDER BY vendor_name
""")
chq_vendors = cur.fetchall()
print(f"\nFound {len(chq_vendors)} CHQ vendors with numbers/details")
for (chq_vendor,) in chq_vendors[:20]:
    print(f"  {chq_vendor}")

# Apply all fixes
print("\n\nApplying fixes:")
total_updated = 0

for old_name, new_name in fixes_to_apply:
    cur.execute("""
        UPDATE receipts
        SET vendor_name = %s
        WHERE vendor_name = %s
    """, (new_name, old_name))
    
    count = cur.rowcount
    if count > 0:
        total_updated += count
        print(f"  ✅ {count:4} receipts: '{old_name}' → '{new_name}'")

conn.commit()

print(f"\n✅ COMMITTED: {total_updated} receipts updated")

cur.close()
conn.close()

print("\n✅ COMPLETE")
