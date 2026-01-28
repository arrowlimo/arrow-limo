#!/usr/bin/env python3
"""
Check banking_transactions vendor names for consistency with receipts standardization.
Identify vendors that need matching standardization.
"""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

print("=" * 80)
print("BANKING TRANSACTIONS VENDOR NAME ANALYSIS")
print("=" * 80)

cur = conn.cursor()

# 1. Get all banking vendors
print("\n1. BANKING VENDOR DISTRIBUTION")
print("-" * 80)

cur.execute("""
    SELECT vendor_extracted, COUNT(*) as count
    FROM banking_transactions
    WHERE vendor_extracted IS NOT NULL AND vendor_extracted != ''
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

banking_vendors = cur.fetchall()
print(f"\nTotal unique banking vendors: {len(banking_vendors)}\n")

for vendor, count in banking_vendors[:30]:
    print(f"{count:5} | {vendor}")

# 2. Check for NULL/empty vendors
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE vendor_extracted IS NULL OR vendor_extracted = ''
""")
null_count = cur.fetchone()[0]
print(f"\nNULL/empty vendors: {null_count:,}")

# 3. Check for vendor patterns that need standardization
print("\n\n2. VENDOR PATTERNS NEEDING STANDARDIZATION")
print("-" * 80)

# Card deposits with variations
cur.execute("""
    SELECT vendor_extracted, COUNT(*) as count
    FROM banking_transactions
    WHERE vendor_extracted LIKE '%CARD DEPOSIT%'
       OR vendor_extracted LIKE '%CARD PAYMENT%'
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

card_vendors = cur.fetchall()
if card_vendors:
    print(f"\nCard transactions: {len(card_vendors)} variations")
    for vendor, count in card_vendors:
        print(f"  {count:5} | {vendor}")

# Cash withdrawals
cur.execute("""
    SELECT vendor_extracted, COUNT(*) as count
    FROM banking_transactions
    WHERE vendor_extracted LIKE '%WITHDRAWAL%'
       OR vendor_extracted LIKE '%ATM%'
       OR vendor_extracted LIKE '%ABM%'
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

withdrawal_vendors = cur.fetchall()
if withdrawal_vendors:
    print(f"\nCash withdrawals: {len(withdrawal_vendors)} variations")
    for vendor, count in withdrawal_vendors:
        print(f"  {count:5} | {vendor}")

# Email transfers
cur.execute("""
    SELECT vendor_extracted, COUNT(*) as count
    FROM banking_transactions
    WHERE vendor_extracted LIKE '%TRANSFER%'
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

transfer_vendors = cur.fetchall()
if transfer_vendors:
    print(f"\nTransfers: {len(transfer_vendors)} variations")
    for vendor, count in transfer_vendors[:10]:
        print(f"  {count:5} | {vendor}")
    if len(transfer_vendors) > 10:
        print(f"  ... and {len(transfer_vendors) - 10} more")

# Fees
cur.execute("""
    SELECT vendor_extracted, COUNT(*) as count
    FROM banking_transactions
    WHERE vendor_extracted LIKE '%FEE%'
       OR vendor_extracted LIKE '%CHARGE%'
       OR vendor_extracted LIKE '%NSF%'
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

fee_vendors = cur.fetchall()
if fee_vendors:
    print(f"\nFees: {len(fee_vendors)} variations")
    for vendor, count in fee_vendors[:10]:
        print(f"  {count:5} | {vendor}")
    if len(fee_vendors) > 10:
        print(f"  ... and {len(fee_vendors) - 10} more")

# 3. Compare with receipts vendors
print("\n\n3. VENDOR CONSISTENCY CHECK")
print("-" * 80)

# Get receipt vendors
cur.execute("""
    SELECT DISTINCT vendor_name
    FROM receipts
    WHERE vendor_name IS NOT NULL AND vendor_name != 'UNKNOWN'
""")
receipt_vendors = set(row[0] for row in cur.fetchall())

# Get banking vendors
cur.execute("""
    SELECT DISTINCT vendor_extracted
    FROM banking_transactions
    WHERE vendor_extracted IS NOT NULL AND vendor_extracted != ''
""")
banking_vendor_set = set(row[0] for row in cur.fetchall())

# Common vendors
common = receipt_vendors & banking_vendor_set
print(f"\nVendors in both receipts and banking: {len(common)}")

# Only in receipts
only_receipts = receipt_vendors - banking_vendor_set
print(f"Vendors only in receipts: {len(only_receipts)}")
if only_receipts:
    print("\nTop 20 receipt-only vendors:")
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count
        FROM receipts
        WHERE vendor_name IN %s
        GROUP BY vendor_name
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """, (tuple(only_receipts),))
    for vendor, count in cur.fetchall():
        print(f"  {count:5} | {vendor}")

# Only in banking
only_banking = banking_vendor_set - receipt_vendors
print(f"\nVendors only in banking: {len(only_banking)}")
if only_banking:
    print("\nTop 20 banking-only vendors:")
    cur.execute("""
        SELECT vendor_extracted, COUNT(*) as count
        FROM banking_transactions
        WHERE vendor_extracted IN %s
        GROUP BY vendor_extracted
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """, (tuple(only_banking),))
    for vendor, count in cur.fetchall():
        print(f"  {count:5} | {vendor}")

# 4. Suggest standardizations
print("\n\n4. SUGGESTED BANKING STANDARDIZATIONS")
print("-" * 80)

suggestions = []

# Check for unstandardized withdrawals
cur.execute("""
    SELECT vendor_extracted, COUNT(*) 
    FROM banking_transactions
    WHERE (vendor_extracted LIKE '%ABM%' OR vendor_extracted LIKE '%ATM%')
      AND vendor_extracted != 'CASH WITHDRAWAL'
    GROUP BY vendor_extracted
""")
withdraw_count = sum(count for _, count in cur.fetchall())
if withdraw_count > 0:
    suggestions.append(f"→ Standardize {withdraw_count} ABM/ATM withdrawals to 'CASH WITHDRAWAL'")

# Check for transfer variations
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE vendor_extracted LIKE '%E-TRANSFER%'
       OR vendor_extracted LIKE '%ETRANSFER%'
       AND vendor_extracted != 'EMAIL TRANSFER'
""")
transfer_count = cur.fetchone()[0]
if transfer_count > 0:
    suggestions.append(f"→ Standardize {transfer_count} e-transfer variations to 'EMAIL TRANSFER'")

# Check for fee variations
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE (vendor_extracted LIKE '%BANK FEE%' OR vendor_extracted LIKE '%SERVICE CHARGE%')
      AND vendor_extracted != 'BANK SERVICE FEE'
""")
fee_count = cur.fetchone()[0]
if fee_count > 0:
    suggestions.append(f"→ Standardize {fee_count} bank fee variations to 'BANK SERVICE FEE'")

if suggestions:
    print("\nRecommended changes:")
    for suggestion in suggestions:
        print(f"  {suggestion}")
else:
    print("\n✅ Banking vendors appear standardized!")

print("\n" + "=" * 80)
total_banking = sum(count for _, count in banking_vendors)
print(f"Total banking transactions with vendors: {total_banking:,}")
print(f"Null/empty vendors: {null_count:,}")
print(f"Total banking transactions: {total_banking + null_count:,}")
print("=" * 80)

cur.close()
conn.close()
