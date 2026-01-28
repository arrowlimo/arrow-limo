#!/usr/bin/env python3
"""
Consolidate specific DEPOSIT variations by their actual purpose
"""
import psycopg2
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Mapping of specific DEPOSIT variations to their actual category
deposit_mappings = {
    'EMAIL MONEY DEPOSIT FEE': 'EMAIL MONEY DEPOSIT FEE',  # Banking fee
    'DEPOSIT FROM IFS': 'IFS NSF REFUND',  # NSF refunded by bank
    'DEPOSIT FROM CIBC ACCOUNT': 'CIBC BANK TRANSFER',  # Transfer between accounts
    'DEPOSIT $1000 FROM CIBC ACCOUNT': 'CIBC BANK TRANSFER',
    'DEPOSIT $500 FROM CIBC': 'CIBC BANK TRANSFER',
    'DEPOSIT $1300 FROM CIBC': 'CIBC BANK TRANSFER',
    'DEPOSIT FROM CIBC': 'CIBC BANK TRANSFER',
    'DEPOSIT FROM CAMBRIDE ON': 'INSURANCE/POLICY REFUND',  # Insurance money back
    'BRANCH TRANSACTION DEPOSIT 188 CLEARVIEW BANKING CENTRE REDD': 'CASH DEPOSIT',
    'BRANCH TRANSACTION DEPOSIT IBB CLEARVIEW BANKING CENTRE REDD': 'CASH DEPOSIT',
    'BRANCH TRANSACTION DEPOSIT IBB GAETZ AVE & 67TH ST BANKING CE': 'CASH DEPOSIT',
    'BRANCH TRANSACTION DEPOSIT IBB GAETZAVE & 67TH ST RED': 'CASH DEPOSIT',
    'CCARD DEPOSIT': 'DCARD DEPOSIT',  # Typo fix
    'DEPOSIT 02239 CLEARVIEW BANKING CENTRE': 'CASH DEPOSIT',  # Cash to cover bills
    'DEPOSIT 00018 2ND AVE. & 21ST ST.': 'CASH DEPOSIT',
}

dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

# Find receipts with these vendor names
updates = []
for old_vendor, new_vendor in deposit_mappings.items():
    cur.execute("""
        SELECT receipt_id, vendor_name
        FROM receipts
        WHERE vendor_name = %s
    """, (old_vendor,))
    
    for receipt_id, vendor_name in cur.fetchall():
        if old_vendor != new_vendor:
            updates.append((receipt_id, vendor_name, new_vendor))

print(f"Found {len(updates)} receipts with deposit variations to consolidate\n")

# Show summary
from collections import Counter
summary = Counter(new_vendor for _, _, new_vendor in updates)
print("CONSOLIDATION SUMMARY")
print("=" * 70)
for vendor, count in sorted(summary.items()):
    print(f"{count:>5} | {vendor}")

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to consolidate deposit variations")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input(f"\nType 'CONSOLIDATE' to update {len(updates)} deposit vendor names: ")
    
    if response != 'CONSOLIDATE':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    print("\n📝 Consolidating deposit variations...")
    for receipt_id, old_vendor, new_vendor in updates:
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE receipt_id = %s
        """, (new_vendor, receipt_id))
    
    conn.commit()
    print(f"   ✅ Updated {len(updates)} vendor names")
    print("\n✅ CONSOLIDATION COMPLETE")

cur.close()
conn.close()
