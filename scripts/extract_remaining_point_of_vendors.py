#!/usr/bin/env python3
"""
Extract vendor names from remaining 1,374 POINT OF receipts.
These are domestic transactions (not INTL/USD).
"""

import psycopg2
import re

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

print("=" * 80)
print("EXTRACTING VENDORS FROM REMAINING POINT OF RECEIPTS")
print("=" * 80)

# Get all POINT OF receipts
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.description,
        bt.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    LEFT JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'POINT OF'
    ORDER BY r.receipt_date DESC
""")

point_of_receipts = cur.fetchall()
print(f"\nFound {len(point_of_receipts)} POINT OF receipts to process\n")

updates = []
no_banking = []
failed_extraction = []

for receipt_id, date, amount, desc, banking_desc in point_of_receipts:
    if not banking_desc:
        no_banking.append((receipt_id, date, amount, desc))
        continue
    
    # Try to extract vendor from banking description
    # Patterns:
    # "Point of Sale - Visa Debit RETAIL PURCHASE <VENDOR>"
    # "Point of Sale - Interac <VENDOR>"
    # "Point of Sale - MasterCard <VENDOR>"
    
    vendor = None
    
    # Pattern 1: RETAIL PURCHASE <VENDOR> <TRANSACTION_ID>
    match = re.search(r'RETAIL PURCHASE\s+([A-Z0-9\s\.\*\-&]+?)\s+\d{12,}', banking_desc)
    if match:
        vendor = match.group(1).strip()
    
    # Pattern 2: INTERAC <TRANSACTION_TYPE> <VENDOR>
    if not vendor:
        match = re.search(r'INTERAC\s+(?:PURCHASE|RETAIL PURCHASE)\s*(\d+)?\s+([A-Z0-9\s\.\*\-&]+)', banking_desc)
        if match:
            vendor = match.group(2).strip()
    
    # Pattern 3: Just grab everything after "Point of Sale -"
    if not vendor:
        match = re.search(r'Point of Sale - (?:Visa Debit|MasterCard|Interac)\s+(.+)', banking_desc, re.IGNORECASE)
        if match:
            vendor = match.group(1).strip()
            # Clean up transaction IDs at the end
            vendor = re.sub(r'\s+\d{12,}.*$', '', vendor)
            vendor = re.sub(r'\s+\d{6,}\s*$', '', vendor)
    
    if vendor:
        # Clean up vendor name
        vendor = vendor.strip()
        # Remove common suffixes
        vendor = re.sub(r'\s+RED DEER\s*$', '', vendor)
        vendor = re.sub(r'\s+ALBERTA\s*$', '', vendor)
        vendor = re.sub(r'\s+AB\s*$', '', vendor)
        vendor = re.sub(r'\s+CANADA\s*$', '', vendor)
        
        # Limit length
        if len(vendor) > 60:
            vendor = vendor[:60].strip()
        
        updates.append((vendor, receipt_id, date, amount, banking_desc[:60]))
    else:
        failed_extraction.append((receipt_id, date, amount, banking_desc[:100]))

print(f"Results:")
print(f"  Successfully extracted: {len(updates)}")
print(f"  No banking description: {len(no_banking)}")
print(f"  Failed extraction: {len(failed_extraction)}")

if updates:
    print(f"\nSample extractions (first 20):")
    for vendor, receipt_id, date, amount, banking in updates[:20]:
        print(f"  {receipt_id} | {date} | {vendor[:40]:40} | ${amount:,.2f}")
    
    print(f"\n\nApplying {len(updates)} vendor extractions...")
    for vendor, receipt_id, _, _, _ in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (vendor, receipt_id))
    
    conn.commit()
    print(f"✅ Updated {len(updates)} POINT OF receipts with vendor names")

if failed_extraction:
    print(f"\n\n⚠️  {len(failed_extraction)} receipts failed extraction:")
    for receipt_id, date, amount, banking in failed_extraction[:10]:
        print(f"  {receipt_id} | {date} | ${amount:,.2f}")
        print(f"    Banking: {banking}")

if no_banking:
    print(f"\n\n⚠️  {len(no_banking)} receipts have no banking description:")
    for receipt_id, date, amount, desc in no_banking[:10]:
        print(f"  {receipt_id} | {date} | ${amount:,.2f} | {desc}")

# Final check
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'POINT OF'")
remaining = cur.fetchone()[0]
print(f"\n\n{remaining} POINT OF receipts remaining after extraction")

cur.close()
conn.close()
