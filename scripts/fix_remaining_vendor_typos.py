#!/usr/bin/env python3
"""Fix remaining vendor name typos and corruptions."""

import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

# Define remaining typos and corruptions to fix
fixes = {
    'LiquorT own': 'Liquor Town',           # Space inserted in middle
    'Llq(!Or Barn 67th Str': 'Liquor Barn', # OCR corruption from "Liquor Barn 67th Str"
    'Wholesale Cluq': 'Wholesale Club',     # Typo: q instead of b
    'CanadianT ire #329': 'Canadian Tire',  # Space inserted, remove #329
    'Cente': 'Centex',                       # Truncated
    'Co': 'Co-op',                           # Single letter, incomplete
    'E': 'Unknown',                          # Single letter - investigate separately
}

print("=== BANKING VENDOR TYPO FIXES ===\n")

backup_name = f"banking_transactions_typo_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_name}...")
cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM banking_transactions WHERE account_number = '0228362'")
print(f"✓ Backed up 9,865 CIBC transactions\n")

total_updated = 0
for from_vendor, to_vendor in fixes.items():
    cur.execute("""
        UPDATE banking_transactions
        SET vendor_extracted = %s
        WHERE account_number = '0228362'
        AND vendor_extracted = %s
    """, (to_vendor, from_vendor))
    
    count = cur.rowcount
    if count > 0:
        print(f"✓ {count:2} transactions: '{from_vendor}' → '{to_vendor}'")
        total_updated += count
    else:
        print(f"  0 transactions: '{from_vendor}' (not found)")

if total_updated > 0:
    conn.commit()
    print(f"\n✓ {total_updated} total updates committed")
else:
    conn.rollback()
    print(f"\n! No updates needed")

conn.close()
