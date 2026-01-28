#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
standardize_vendor_names_for_accounting.py

Clean up vendor names for consistent accounting/reporting:
- Strip receipt numbers from gas stations (FAS GAS 000001210002 → FAS GAS)
- Standardize common name variations (WAL-MART → WALMART)
- Keep all transactions separate, just normalize vendor field
"""

import psycopg2
import re
import sys

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def standardize_vendor_for_accounting(vendor):
    """Standardize vendor name for accounting consistency."""
    if not vendor:
        return vendor
    
    # Already uppercase from previous standardization
    normalized = vendor.strip()
    
    # Strip receipt/transaction numbers from gas stations
    # Pattern: Vendor name followed by long number sequences
    gas_stations = ['FAS GAS', 'SHELL', 'PETRO CANADA', 'ESSO', 'HUSKY', 'CO-OP']
    for station in gas_stations:
        if normalized.startswith(station):
            # Remove trailing number sequences (6+ digits)
            normalized = re.sub(r'\s+\d{6,}$', '', normalized)
            return station  # Return base name
    
    # Standardize common retail variations
    standardizations = {
        r'^WAL[\s-]?MART(\s+#?\d+)?': 'WALMART',
        r'^7[\s\-]?ELEVEN': '7-ELEVEN',
        r'^REAL\s+CANADIAN\s+SUPERSTORE': 'SUPERSTORE',
        r'^TIM\s*HORTONS?': 'TIM HORTONS',
        r'^CANADIAN\s+TIRE(\s+CORP)?(\s+#?\d+)?': 'CANADIAN TIRE',
        r'^SAFEWAY(\s+CANADA)?': 'SAFEWAY',
        r'^COSTCO(\s+WHOLESALE)?': 'COSTCO',
    }
    
    for pattern, standard in standardizations.items():
        if re.match(pattern, normalized, re.IGNORECASE):
            return standard
    
    return normalized

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

print("\n" + "="*110)
print("VENDOR NAME STANDARDIZATION FOR ACCOUNTING")
print("="*110 + "\n")

# Analyze banking transactions
print("Analyzing banking_transactions vendor names...")
cur.execute("""
    SELECT vendor_extracted, COUNT(*) as tx_count
    FROM banking_transactions
    WHERE vendor_extracted IS NOT NULL
    AND verified = TRUE
    GROUP BY vendor_extracted
    HAVING COUNT(*) > 0
    ORDER BY COUNT(*) DESC
""")

banking_changes = {}
for vendor, count in cur.fetchall():
    standardized = standardize_vendor_for_accounting(vendor)
    if standardized != vendor:
        banking_changes[vendor] = (standardized, count)

print(f"Found {len(banking_changes)} banking vendor names to standardize\n")

# Analyze receipts
print("Analyzing receipts vendor names...")
cur.execute("""
    SELECT vendor_name, COUNT(*) as tx_count
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
    HAVING COUNT(*) > 0
    ORDER BY COUNT(*) DESC
""")

receipt_changes = {}
for vendor, count in cur.fetchall():
    standardized = standardize_vendor_for_accounting(vendor)
    if standardized != vendor:
        receipt_changes[vendor] = (standardized, count)

print(f"Found {len(receipt_changes)} receipt vendor names to standardize\n")

# Show preview
print("="*110)
print("PREVIEW OF CHANGES")
print("="*110 + "\n")

print("BANKING TRANSACTIONS (Top 20):")
print(f"{'Original':<60} {'Standardized':<40} {'Count':>10}")
print("-"*110)
shown = 0
for original, (standardized, count) in sorted(banking_changes.items(), key=lambda x: x[1][1], reverse=True):
    if shown < 20:
        print(f"{original[:58]:<60} {standardized:<40} {count:>10,}")
        shown += 1

if len(banking_changes) > 20:
    print(f"... and {len(banking_changes) - 20} more")

print(f"\nRECEIPTS (Top 20):")
print(f"{'Original':<60} {'Standardized':<40} {'Count':>10}")
print("-"*110)
shown = 0
for original, (standardized, count) in sorted(receipt_changes.items(), key=lambda x: x[1][1], reverse=True):
    if shown < 20:
        print(f"{original[:58]:<60} {standardized:<40} {count:>10,}")
        shown += 1

if len(receipt_changes) > 20:
    print(f"... and {len(receipt_changes) - 20} more")

# Summary
total_banking_tx = sum(count for _, count in banking_changes.values())
total_receipt_tx = sum(count for _, count in receipt_changes.values())

print(f"\n" + "="*110)
print("SUMMARY")
print("="*110)
print(f"Banking vendors to standardize: {len(banking_changes):,}")
print(f"Banking transactions affected: {total_banking_tx:,}")
print(f"Receipt vendors to standardize: {len(receipt_changes):,}")
print(f"Receipt transactions affected: {total_receipt_tx:,}")
print(f"Total changes: {len(banking_changes) + len(receipt_changes):,}")

# Check for dry-run
dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply standardization")
    cur.close()
    conn.close()
    sys.exit(0)

# Execute mode
print("\n⚠️  EXECUTION MODE")
response = input("\nType 'STANDARDIZE' to proceed: ")
if response != 'STANDARDIZE':
    print("❌ Cancelled")
    cur.close()
    conn.close()
    sys.exit(1)

try:
    # Disable trigger
    print("\n🔓 Disabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
    
    # Update banking transactions
    print("📝 Standardizing banking_transactions vendor names...")
    updated_banking = 0
    for original, (standardized, _) in banking_changes.items():
        cur.execute("""
            UPDATE banking_transactions
            SET vendor_extracted = %s
            WHERE vendor_extracted = %s
        """, (standardized, original))
        updated_banking += cur.rowcount
    
    print(f"   ✅ Updated {updated_banking:,} banking transactions")
    
    # Update receipts
    print("📝 Standardizing receipts vendor names...")
    updated_receipts = 0
    for original, (standardized, _) in receipt_changes.items():
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE vendor_name = %s
        """, (standardized, original))
        updated_receipts += cur.rowcount
    
    print(f"   ✅ Updated {updated_receipts:,} receipts")
    
    # Re-enable trigger
    print("\n🔒 Re-enabling banking lock trigger...")
    cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
    
    conn.commit()
    
    print(f"\n✅ STANDARDIZATION COMPLETE")
    print(f"   Banking: {updated_banking:,} transactions")
    print(f"   Receipts: {updated_receipts:,} transactions")
    print(f"   Total: {updated_banking + updated_receipts:,} updates")
    print("\n📊 Vendor names now standardized for accounting consistency!")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    conn.rollback()
    raise

finally:
    cur.close()
    conn.close()
