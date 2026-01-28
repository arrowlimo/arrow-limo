#!/usr/bin/env python3
"""
Extract vendor names from POINT OF receipt descriptions.
The vendor name is embedded in the description after the transaction ID.
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
print("EXTRACTING VENDORS FROM POINT OF DESCRIPTIONS")
print("=" * 80)

# Get all POINT OF receipts with descriptions
cur.execute("""
    SELECT receipt_id, description
    FROM receipts
    WHERE vendor_name = 'POINT OF'
      AND description IS NOT NULL
      AND description != ''
    ORDER BY receipt_id
""")

receipts = cur.fetchall()
print(f"\nFound {len(receipts)} POINT OF receipts with descriptions")

updates = []
failed = []

for receipt_id, desc in receipts:
    vendor = None
    
    # Pattern 1: RETAIL PURCHASE <TRANSACTION_ID> <VENDOR>
    match = re.search(r'RETAIL PURCHASE\s+(\d+)\s+(.+?)(?:\s+RED\s+DE|\s+RED\s+DEER|\s*$)', desc, re.IGNORECASE)
    if match:
        vendor = match.group(2).strip()
    
    # Pattern 2: After transaction ID, before location
    if not vendor:
        match = re.search(r'\d{12,}\s+(.+?)(?:\s+RED\s+|$)', desc)
        if match:
            vendor = match.group(1).strip()
    
    # Pattern 3: Just grab everything after PURCHASE and transaction ID
    if not vendor:
        match = re.search(r'PURCHASE\s+\d+\s+(.+)', desc, re.IGNORECASE)
        if match:
            vendor = match.group(1).strip()
    
    if vendor:
        # Clean up vendor name
        vendor = vendor.strip()
        # Remove location suffixes
        vendor = re.sub(r'\s+RED\s+DE.*$', '', vendor, flags=re.IGNORECASE)
        vendor = re.sub(r'\s+RED\s+DEER.*$', '', vendor, flags=re.IGNORECASE)
        vendor = re.sub(r'\s+ALBERTA.*$', '', vendor, flags=re.IGNORECASE)
        vendor = re.sub(r'\s+AB\s*$', '', vendor, flags=re.IGNORECASE)
        vendor = re.sub(r'\s+CANADA.*$', '', vendor, flags=re.IGNORECASE)
        
        # Limit to 60 characters
        if len(vendor) > 60:
            vendor = vendor[:60].strip()
        
        # Skip if vendor is empty or just numbers
        if vendor and not vendor.isdigit() and len(vendor) > 2:
            updates.append((vendor, receipt_id, desc[:80]))
        else:
            failed.append((receipt_id, desc[:100]))
    else:
        failed.append((receipt_id, desc[:100]))

print(f"\nExtraction results:")
print(f"  Successful: {len(updates):,}")
print(f"  Failed: {len(failed):,}")

if updates:
    print(f"\nSample extractions (first 30):")
    for vendor, receipt_id, desc in updates[:30]:
        print(f"  {receipt_id}: {vendor[:50]}")
    
    print(f"\n\nApplying {len(updates):,} updates...")
    for vendor, receipt_id, _ in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (vendor, receipt_id))
    
    conn.commit()
    print(f"✅ Updated {len(updates):,} receipts")

if failed:
    print(f"\n⚠️  {len(failed)} receipts failed extraction:")
    for receipt_id, desc in failed[:10]:
        print(f"  {receipt_id}: {desc}")

# Final count
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'POINT OF'")
remaining = cur.fetchone()[0]
print(f"\n\nPOINT OF receipts remaining: {remaining:,}")

cur.close()
conn.close()
