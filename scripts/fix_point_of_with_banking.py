#!/usr/bin/env python3
"""
Fix the 210 POINT OF receipts that HAVE banking but failed extraction.
Use improved regex patterns to extract vendor names.
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
print("FIXING 210 POINT OF RECEIPTS WITH BANKING MATCHES")
print("=" * 80)

# Get POINT OF receipts WITH banking matches
cur.execute("""
    SELECT 
        r.receipt_id,
        r.gross_amount,
        bt.description as banking_desc
    FROM receipts r
    JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
    JOIN banking_transactions bt ON brml.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'POINT OF'
    ORDER BY r.receipt_id
""")

receipts = cur.fetchall()
print(f"\nFound {len(receipts)} POINT OF receipts with banking to process\n")

updates = []
failed = []

for receipt_id, amount, banking_desc in receipts:
    vendor = None
    
    # Pattern 1: PURCHASE<DIGITS> <VENDOR> <4506>
    match = re.search(r'PURCHASE\s*(\d+)\s+([A-Z0-9\s\.\*\-&\#]+?)\s+4506', banking_desc, re.IGNORECASE)
    if match:
        vendor = match.group(2).strip()
    
    # Pattern 2: RETAIL PURCHASE <DIGITS> <VENDOR>
    if not vendor:
        match = re.search(r'RETAIL PURCHASE\s+(\d+)\s+(.+?)(?:\s+RED\s|\s*$)', banking_desc, re.IGNORECASE)
        if match:
            vendor = match.group(2).strip()
    
    # Pattern 3: After any long digit sequence
    if not vendor:
        match = re.search(r'\d{10,}\s+([A-Z0-9\s\.\*\-&\#]+)', banking_desc)
        if match:
            vendor = match.group(1).strip()
    
    if vendor:
        # Clean up
        vendor = re.sub(r'\s+RED\s+DE.*$', '', vendor, flags=re.IGNORECASE)
        vendor = re.sub(r'\s+ALBERTA.*$', '', vendor, flags=re.IGNORECASE)
        vendor = re.sub(r'\s+4506\*+\d+.*$', '', vendor)
        vendor = vendor[:60].strip()
        
        if vendor and len(vendor) > 1 and not vendor.isdigit():
            updates.append((vendor, receipt_id, banking_desc[:60]))
        else:
            failed.append((receipt_id, amount, banking_desc))
    else:
        failed.append((receipt_id, amount, banking_desc))

print(f"Extraction results:")
print(f"  Success: {len(updates):,}")
print(f"  Failed: {len(failed):,}")

if updates:
    print(f"\nSample extractions (first 40):")
    for vendor, receipt_id, banking in updates[:40]:
        print(f"  {receipt_id}: {vendor}")
    
    print(f"\n\nApplying {len(updates):,} updates...")
    for vendor, receipt_id, _ in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (vendor, receipt_id))
    
    conn.commit()
    print(f"✅ Updated {len(updates):,} POINT OF receipts")

if failed:
    print(f"\n⚠️  {len(failed)} still failed:")
    for receipt_id, amount, banking in failed[:20]:
        print(f"  {receipt_id} ${amount:.2f}: {banking[:80]}")

# Final check
cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name = 'POINT OF'")
remaining = cur.fetchone()[0]
print(f"\n\nPOINT OF receipts remaining: {remaining:,}")

cur.close()
conn.close()
