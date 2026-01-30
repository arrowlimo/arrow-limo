#!/usr/bin/env python3
"""
For POINT OF receipts WITHOUT descriptions, extract vendor from banking_transactions.
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
print("EXTRACTING VENDORS FROM BANKING FOR POINT OF (NO DESCRIPTION)")
print("=" * 80)

# Get POINT OF receipts without descriptions but with banking match
cur.execute("""
    SELECT 
        r.receipt_id,
        r.gross_amount,
        bt.description as banking_desc
    FROM receipts r
    JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'POINT OF'
      AND (r.description IS NULL OR r.description = '' OR r.description = 'NaN')
    ORDER BY r.receipt_id
""")

receipts = cur.fetchall()
print(f"\nFound {len(receipts)} POINT OF receipts with banking but no description")

updates = []
failed = []

for receipt_id, amount, banking_desc in receipts:
    vendor = None
    
    # Pattern: RETAIL PURCHASE <TRANSACTION_ID> <VENDOR>
    match = re.search(r'(?:RETAIL PURCHASE|INTERAC)\s+(\d+)\s+(.+?)(?:\s+RED\s|$)', banking_desc, re.IGNORECASE)
    if match:
        vendor = match.group(2).strip()
    
    # Alternative: Everything after transaction ID
    if not vendor:
        match = re.search(r'\d{10,}\s+(.+)', banking_desc)
        if match:
            vendor = match.group(1).strip()
    
    if vendor:
        # Clean vendor name
        vendor = re.sub(r'\s+RED\s+DE.*$', '', vendor, flags=re.IGNORECASE)
        vendor = re.sub(r'\s+ALBERTA.*$', '', vendor, flags=re.IGNORECASE)
        vendor = vendor[:60].strip()
        
        if vendor and len(vendor) > 2 and not vendor.isdigit():
            updates.append((vendor, receipt_id, banking_desc[:80]))
        else:
            failed.append((receipt_id, amount, banking_desc[:100]))
    else:
        failed.append((receipt_id, amount, banking_desc[:100]))

print(f"\nResults:")
print(f"  Successful: {len(updates):,}")
print(f"  Failed: {len(failed):,}")

if updates:
    print(f"\nSample extractions (first 30):")
    for vendor, receipt_id, banking in updates[:30]:
        print(f"  {receipt_id}: {vendor[:50]}")
    
    print(f"\n\nApplying {len(updates):,} updates...")
    for vendor, receipt_id, _ in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (vendor, receipt_id))
    
    conn.commit()
    print(f"✅ Updated {len(updates):,} receipts from banking descriptions")

if failed:
    print(f"\n⚠️  {len(failed)} failed (will keep as POINT OF):")
    for receipt_id, amount, banking in failed[:15]:
        print(f"  {receipt_id} ${amount:.2f}: {banking}")

# Final count
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'POINT OF'")
remaining = cur.fetchone()[0]
print(f"\n\n✅ POINT OF receipts remaining: {remaining:,}")

cur.close()
conn.close()
