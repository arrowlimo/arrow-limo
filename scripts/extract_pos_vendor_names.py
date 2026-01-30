#!/usr/bin/env python3
"""
Extract vendor names from POINT OF SALE banking descriptions
Many receipts have truncated vendor names - need to extract from banking
"""
import psycopg2
import re
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

def extract_vendor_from_banking(banking_desc):
    """Extract actual vendor name from banking description - wrap in brackets to mark as uncertain"""
    if not banking_desc:
        return None
    
    # Remove card number suffix
    banking_desc = re.sub(r'4506\*+\d{3,4}$', '', banking_desc).strip()
    
    # Pattern: transaction_number VENDOR_NAME
    # Match: number followed by alphabetic vendor name
    match = re.search(r'\d{12,}\s+([A-Z][A-Z\s\-&*#\.]+?)(?:\s*-?\s*)?$', banking_desc, re.IGNORECASE)
    if match:
        vendor = match.group(1).strip()
        # Clean up trailing characters
        vendor = re.sub(r'[\s\-]+$', '', vendor)
        if len(vendor) > 2:  # Meaningful vendor name
            return f"[{vendor.upper()}]"  # Brackets = uncertain, needs verification
    
    # Pattern: ends with short code like "604" or "601" (store codes)
    if re.search(r'\d{12,}\s+\d{3}\s*-?$', banking_desc):
        code_match = re.search(r'(\d{3})\s*-?$', banking_desc)
        if code_match:
            code = code_match.group(1)
            if code == '604':
                return 'LIQUOR BARN'  # 604 = Liquor Barn on 64 St Red Deer (known location)
            elif code == '601':
                return '[LIQUOR DEPOT]'  # 601 likely another liquor store (uncertain)
            else:
                return f'[STORE {code}]'
    
    # Pattern: abbreviated vendor at end (KAL-, BED, FAS, etc.)
    if re.search(r'\d{12,}\s+([A-Z]{2,})\s*-?$', banking_desc):
        abbrev_match = re.search(r'(\w{2,})\s*-?$', banking_desc)
        if abbrev_match:
            abbrev = abbrev_match.group(1).upper()
            # Known abbreviations - wrap in brackets to mark as guessed
            if abbrev.startswith('KAL'):
                return '[KAL TIRE]'
            elif abbrev.startswith('FAS'):
                return '[FAS GAS]'
            elif abbrev.startswith('WAL'):
                return '[WALMART]'
            elif abbrev.startswith('BED'):
                return '[BED BATH & BEYOND]'
            elif abbrev == 'TIM':
                return '[TIM HORTONS]'
            elif abbrev == 'THE':
                return '[THE BRICK]'
            elif abbrev.startswith('REAL') or 'CON' in banking_desc:
                return '[REAL CANADIAN SUPERSTORE]'
            elif abbrev == 'TONY':
                return '[TONY ROMAS]'
            elif abbrev == 'WOK':
                return '[WOK BOX]'
            elif abbrev == 'OLD':
                return '[OLD SPAGHETTI FACTORY]'
            elif abbrev == 'RED':
                return '[RED LOBSTER]'
            elif abbrev == 'EAST':
                return '[EAST SIDE MARIOS]'
            elif abbrev == 'ALL':
                return '[ALLSTATE]'
            else:
                return f'[UNKNOWN - {abbrev}]'
    
    # If nothing found, keep as generic POINT OF SALE
    return None

# Preview mode by default
dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

# Get all POINT OF SALE receipts with linked banking
cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        bt.description as banking_desc
    FROM receipts r
    INNER JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE (r.vendor_name ILIKE '%point%of%sale%' OR r.vendor_name ILIKE '%pointofsale%')
      AND r.vendor_name NOT ILIKE '%peavey%'
      AND r.vendor_name NOT ILIKE '%pack%post%'
    ORDER BY r.receipt_id
""")

updates = []
vendor_summary = {}

for receipt_id, current_vendor, banking_desc in cur.fetchall():
    extracted_vendor = extract_vendor_from_banking(banking_desc)
    if extracted_vendor and extracted_vendor != current_vendor:
        updates.append((receipt_id, current_vendor, extracted_vendor, banking_desc))
        vendor_summary[extracted_vendor] = vendor_summary.get(extracted_vendor, 0) + 1

print(f"Found {len(updates)} POINT OF SALE receipts with extractable vendor names\n")

# Show summary by extracted vendor
print("EXTRACTED VENDOR SUMMARY")
print("=" * 80)
for vendor, count in sorted(vendor_summary.items(), key=lambda x: -x[1]):
    print(f"{count:>5} | {vendor}")

print("\n" + "=" * 120)
print("Sample updates (first 30):")
print("=" * 120)
for i, (receipt_id, old_vendor, new_vendor, banking_desc) in enumerate(updates[:30]):
    print(f"{new_vendor:<35} | {banking_desc[:80]}")

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to update vendor names from banking descriptions")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input(f"\nType 'EXTRACT' to update {len(updates)} POINT OF SALE receipts: ")
    
    if response != 'EXTRACT':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    print("\n📝 Updating POINT OF SALE vendor names...")
    for receipt_id, old_vendor, new_vendor, banking_desc in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (new_vendor, receipt_id))
    
    conn.commit()
    print(f"   ✅ Updated {len(updates)} receipts with extracted vendor names")
    print("\n✅ EXTRACTION COMPLETE")

cur.close()
conn.close()
