#!/usr/bin/env python3
"""
Fix vague vendor names based on research findings.
"""

import psycopg2
import re

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("FIXING VAGUE VENDOR NAMES")
print("=" * 80)

# 1. Fix POINT OF by extracting actual vendor from banking description
print("\n1. EXTRACTING VENDORS FROM 'POINT OF'")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        b.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'POINT OF'
      AND b.description IS NOT NULL
""")

point_of_receipts = cur.fetchall()
print(f"Found {len(point_of_receipts)} POINT OF receipts with banking data")

point_of_updates = 0
for r_id, b_desc in point_of_receipts:
    # Extract vendor from banking description
    # Pattern: "Point of Sale - Interac RETAIL PURCHASE 000001826003 ERLES AUTO REPA"
    # or: "Point of Sale - Interac PURCHASE312413986970 GREGG'S PAINT A 4506*****"
    
    vendor = None
    
    # Try to extract vendor name after the purchase code
    match = re.search(r'PURCHASE\s+\d+\s+([A-Z\s&\']+?)(?:\s+4506|\s*$)', b_desc)
    if match:
        vendor = match.group(1).strip()
    else:
        match = re.search(r'RETAIL PURCHASE\s+\d+\s+([A-Z\s&\']+?)(?:\s+4506|\s*$)', b_desc)
        if match:
            vendor = match.group(1).strip()
    
    if vendor:
        # Clean up vendor name
        vendor = vendor.strip()
        
        # Update receipt
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (vendor, r_id))
        
        point_of_updates += 1

conn.commit()
print(f"✅ Updated {point_of_updates} receipts from POINT OF")

# 2. Fix COULD BE CAPS OR COOP by checking description
print("\n2. FIXING 'COULD BE CAPS OR COOP'")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.description,
        b.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'COULD BE CAPS OR COOP'
""")

caps_coop = cur.fetchall()
for r_id, r_desc, b_desc in caps_coop:
    print(f"  Receipt desc: {r_desc}")
    print(f"  Banking desc: {b_desc}")
    
    # Check if it's COOP
    if b_desc and 'CO-OP' in b_desc.upper():
        cur.execute("UPDATE receipts SET vendor_name = 'CO-OP' WHERE receipt_id = %s", (r_id,))
    elif b_desc and 'CAPS' in b_desc.upper():
        cur.execute("UPDATE receipts SET vendor_name = 'CAPS' WHERE receipt_id = %s", (r_id,))
    else:
        # Default to CO-OP (gas station)
        cur.execute("UPDATE receipts SET vendor_name = 'CO-OP' WHERE receipt_id = %s", (r_id,))

conn.commit()
print(f"✅ Fixed {len(caps_coop)} CAPS/COOP receipts")

# 3. Fix CAPS by checking if it's actually COOP
print("\n3. FIXING SINGLE 'CAPS' VENDOR")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.description,
        b.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'CAPS'
""")

caps_single = cur.fetchall()
for r_id, r_desc, b_desc in caps_single:
    print(f"  Receipt desc: {r_desc}")
    print(f"  Banking desc: {b_desc}")
    
    # Default to CO-OP (likely gas station)
    cur.execute("UPDATE receipts SET vendor_name = 'CO-OP' WHERE receipt_id = %s", (r_id,))

conn.commit()
print(f"✅ Fixed {len(caps_single)} CAPS receipts → CO-OP")

# 4. Fix BANKING TRANSACTION (opening balances)
print("\n4. FIXING 'BANKING TRANSACTION'")
print("-" * 80)

cur.execute("""
    UPDATE receipts
    SET vendor_name = 'OPENING BALANCE'
    WHERE vendor_name = 'BANKING TRANSACTION'
      AND (description LIKE '%Opening Balance%' OR gross_amount = 0)
""")

banking_trans_count = cur.rowcount
conn.commit()
print(f"✅ Fixed {banking_trans_count} BANKING TRANSACTION → OPENING BALANCE")

# 5. Consolidate CO-OP- LIQUOR into CO-OP
print("\n5. CONSOLIDATING CO-OP VARIATIONS")
print("-" * 80)

cur.execute("""
    UPDATE receipts
    SET vendor_name = 'CO-OP'
    WHERE vendor_name = 'CO-OP- LIQUOR'
""")

coop_liquor = cur.rowcount
conn.commit()
print(f"✅ Fixed {coop_liquor} CO-OP- LIQUOR → CO-OP")

# 6. Fix BRANCH TRANSACTION to be more specific
print("\n6. FIXING 'BRANCH TRANSACTION'")
print("-" * 80)

# Overdraft fees
cur.execute("""
    UPDATE receipts
    SET vendor_name = 'OVERDRAFT FEE'
    WHERE vendor_name = 'BRANCH TRANSACTION'
      AND description LIKE '%OVERDRAFT FEE%'
""")
od_count = cur.rowcount

# Bank fees
cur.execute("""
    UPDATE receipts
    SET vendor_name = 'BANK SERVICE FEE'
    WHERE vendor_name = 'BRANCH TRANSACTION'
      AND (description LIKE '%FEES/FRAIS%' OR description LIKE '%DEBIT MEMO%')
""")
fee_count = cur.rowcount

conn.commit()
print(f"✅ Fixed {od_count} BRANCH TRANSACTION → OVERDRAFT FEE")
print(f"✅ Fixed {fee_count} BRANCH TRANSACTION → BANK SERVICE FEE")

# 7. Fix DEPOSIT (UNSPECIFIED) - they're all $0 DEBIT CD
print("\n7. FIXING 'DEPOSIT (UNSPECIFIED)'")
print("-" * 80)

cur.execute("""
    UPDATE receipts
    SET vendor_name = 'JOURNAL ENTRY (DEBIT CD)'
    WHERE vendor_name = 'DEPOSIT (UNSPECIFIED)'
      AND gross_amount = 0
""")

deposit_count = cur.rowcount
conn.commit()
print(f"✅ Fixed {deposit_count} DEPOSIT (UNSPECIFIED) → JOURNAL ENTRY (DEBIT CD)")

# 8. Fix short vendor names that should be expanded
print("\n8. EXPANDING SHORT VENDOR NAMES")
print("-" * 80)

expansions = [
    ('ROGER', 'ROGERS'),  # Consolidate ROGER and ROGERS
    ('RCSS', 'REAL CANADIAN SUPERSTORE'),
    ('MARKS', "MARK'S WORK WEARHOUSE"),
    ('WENDYS', "WENDY'S"),  # Consolidate WENDYS and WENDY'S
]

for short, full in expansions:
    cur.execute("""
        UPDATE receipts
        SET vendor_name = %s
        WHERE vendor_name = %s
    """, (full, short))
    
    count = cur.rowcount
    if count > 0:
        print(f"✅ Fixed {count:3} {short} → {full}")

conn.commit()

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_fixed = (point_of_updates + len(caps_coop) + len(caps_single) + 
               banking_trans_count + coop_liquor + od_count + fee_count + deposit_count)

print(f"\nTotal receipts fixed: {total_fixed}+")
print("  - POINT OF extracted: {point_of_updates}")
print(f"  - CAPS/COOP resolved: {len(caps_coop) + len(caps_single)}")
print(f"  - BANKING TRANSACTION → OPENING BALANCE: {banking_trans_count}")
print(f"  - BRANCH TRANSACTION split: {od_count + fee_count}")
print(f"  - DEPOSIT (UNSPECIFIED) → JOURNAL ENTRY: {deposit_count}")
print(f"  - Short names expanded")

cur.close()
conn.close()

print("\n✅ COMPLETE")
