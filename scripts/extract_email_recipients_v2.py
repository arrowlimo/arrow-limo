#!/usr/bin/env python3
"""Extract EMAIL TRANSFER recipients from banking descriptions (enhanced pass 2)."""

import psycopg2
import os
import re

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("EMAIL TRANSFER RECIPIENT EXTRACTION - PASS 2 (Enhanced)")
print("=" * 100)

# Find all generic EMAIL TRANSFER entries
cur.execute("""
    SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.receipt_date,
           bt.description as banking_desc, bt.transaction_id
    FROM receipts r
    LEFT JOIN banking_transactions bt ON bt.receipt_id = r.receipt_id
    WHERE r.vendor_name = 'EMAIL TRANSFER'
    ORDER BY r.receipt_date
""")
email_transfers = cur.fetchall()
print(f"\nFound {len(email_transfers)} generic EMAIL TRANSFER receipts")

# Enhanced regex patterns for recipient extraction
patterns = [
    # Modern Internet Banking format: "Internet Banking E-TRANSFER105638419536 Name 4506" or with space
    (r'Internet Banking E-TRANSFER\s*\d+\s+([A-Za-z][A-Za-z\s\.]+?)(?:\s+\d{4}|$)', 'INTERNET BANKING'),
    # E-TRANSFER patterns
    (r'E-?TRANSFER\s+(?:TO|FROM)\s+([A-Z][A-Z\s\.]+?)(?:\s|$)', 'E-TRANSFER'),
    (r'E-TRANSFER\s+([A-Z][A-Za-z\s\.]+?)(?:\s|$)', 'E-TRANSFER NAME'),
    (r'EMAIL\s+(?:MONEY\s+)?TRANSFER\s+-\s+([A-Z][A-Z\s\.]+?)(?:\s|$)', 'EMAIL TRANSFER'),
    (r'EMAIL\s+TRANSFER\s+([A-Z][A-Z\s\.]+?)(?:\s|$)', 'EMAIL TRANSFER'),
    (r'INTERAC\s+E-?TRANSFER\s+([A-Z][A-Z\s\.]+?)(?:\s|$)', 'INTERAC'),
    (r'(?:TO|FROM)\s+([A-Z][A-Z\s\.]{5,})(?:\s+\d{4}|\s*$)', 'NAME PATTERN'),
]

updated = 0
skipped_no_banking = 0
skipped_no_match = 0

for receipt_id, vendor, amount, rdate, banking_desc, tx_id in email_transfers:
    if not banking_desc:
        skipped_no_banking += 1
        continue
    
    # Try each pattern
    recipient = None
    for pattern, pattern_name in patterns:
        match = re.search(pattern, banking_desc, re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            # Clean up recipient name
            recipient = re.sub(r'\s+', ' ', recipient)  # Normalize spaces
            # Skip if it's just "One-time contact" or similar
            if recipient.lower() in ['one-time contact', 'contact', 'etransfer fee']:
                continue
            recipient = recipient.title()  # Proper capitalization
            break
    
    if recipient:
        new_vendor = f"EMAIL TRANSFER - {recipient}"
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (new_vendor, receipt_id))
        updated += 1
        amt_str = f"${amount:,.2f}" if amount else "NULL"
        print(f"   ✓ {receipt_id}: {amt_str:>12} | {rdate} | {recipient[:40]}")
    else:
        skipped_no_match += 1

conn.commit()

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total generic EMAIL TRANSFER: {len(email_transfers)}")
print(f"✅ Updated with recipients: {updated}")
print(f"⚠️  No banking link: {skipped_no_banking}")
print(f"❌ No pattern match: {skipped_no_match}")
print(f"\nRemaining generic EMAIL TRANSFER: {len(email_transfers) - updated}")

# Show remaining
if skipped_no_match > 0:
    print(f"\nSample banking descriptions that didn't match (first 10):")
    cur.execute("""
        SELECT r.receipt_id, bt.description, r.gross_amount
        FROM receipts r
        LEFT JOIN banking_transactions bt ON bt.receipt_id = r.receipt_id
        WHERE r.vendor_name = 'EMAIL TRANSFER'
        AND bt.description IS NOT NULL
        LIMIT 10
    """)
    for rid, desc, amt in cur.fetchall():
        amt_str = f"${amt:,.2f}" if amt else "NULL"
        print(f"   Receipt {rid} ({amt_str:>12}): {desc[:80]}")

cur.close()
conn.close()
