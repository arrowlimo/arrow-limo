#!/usr/bin/env python3
"""
Audit vendor name standardization across receipts and banking_transactions.
Check for remaining variations, duplicates, and non-standardized names.
Exclude internal transfers between our own accounts.
"""

import psycopg2
from collections import defaultdict
import difflib

# Database connection
conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

print("=" * 80)
print("VENDOR NAME STANDARDIZATION AUDIT")
print("=" * 80)

# Exclude patterns for internal transfers
INTERNAL_TRANSFER_PATTERNS = [
    'TRANSFER TO 8362',
    'TRANSFER FROM 8362',
    'TRANSFER TO 903990106011',
    'TRANSFER FROM 903990106011',
    'INTER ACCOUNT TRANSFER',
    'INTERAC TRANSFER',
    'E-TRANSFER',
    'ETRANSFER',
    'ELECTRONIC FUNDS TRANSFER'
]

def is_internal_transfer(vendor):
    """Check if vendor is an internal transfer that should be excluded."""
    if not vendor:
        return False
    vendor_upper = vendor.upper()
    for pattern in INTERNAL_TRANSFER_PATTERNS:
        if pattern in vendor_upper:
            return True
    return False

def similar_strings(s1, s2):
    """Check if two strings are similar (for fuzzy matching)."""
    return difflib.SequenceMatcher(None, s1.upper(), s2.upper()).ratio()

# 1. Check receipts vendor standardization
print("\n1. RECEIPTS VENDOR ANALYSIS")
print("-" * 80)

cur = conn.cursor()
cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        MIN(receipt_date) as first_date,
        MAX(receipt_date) as last_date
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")

receipt_vendors = {}
for row in cur.fetchall():
    vendor, count, first_date, last_date = row
    if not is_internal_transfer(vendor):
        receipt_vendors[vendor] = {
            'count': count,
            'first_date': first_date,
            'last_date': last_date
        }

print(f"Total unique receipt vendors (excluding internal transfers): {len(receipt_vendors)}")

# Check for potential duplicates in receipts
print("\nChecking for similar vendor names in receipts...")
potential_duplicates = []
vendors_list = list(receipt_vendors.keys())

for i, vendor1 in enumerate(vendors_list):
    for vendor2 in vendors_list[i+1:]:
        similarity = similar_strings(vendor1, vendor2)
        if 0.85 <= similarity < 1.0:  # Very similar but not identical
            count1 = receipt_vendors[vendor1]['count']
            count2 = receipt_vendors[vendor2]['count']
            potential_duplicates.append({
                'vendor1': vendor1,
                'vendor2': vendor2,
                'similarity': similarity,
                'count1': count1,
                'count2': count2,
                'total': count1 + count2
            })

if potential_duplicates:
    print(f"\n⚠️  Found {len(potential_duplicates)} potential duplicate vendor pairs in receipts:")
    # Sort by total count (most impactful first)
    potential_duplicates.sort(key=lambda x: x['total'], reverse=True)
    for i, dup in enumerate(potential_duplicates[:20], 1):  # Show top 20
        print(f"\n{i}. Similarity: {dup['similarity']:.1%}")
        print(f"   '{dup['vendor1']}' ({dup['count1']} receipts)")
        print(f"   '{dup['vendor2']}' ({dup['count2']} receipts)")
        print(f"   Total impact: {dup['total']} receipts")
    if len(potential_duplicates) > 20:
        print(f"\n   ... and {len(potential_duplicates) - 20} more pairs")
else:
    print("✅ No similar vendor names found in receipts")

# Check for vendors with numbers (receipt IDs)
print("\n\nChecking for receipt numbers still in vendor names...")
vendors_with_numbers = []
for vendor in receipt_vendors.keys():
    # Look for 6+ consecutive digits
    import re
    if re.search(r'\d{6,}', vendor):
        vendors_with_numbers.append((vendor, receipt_vendors[vendor]['count']))

if vendors_with_numbers:
    print(f"\n⚠️  Found {len(vendors_with_numbers)} vendors with receipt numbers:")
    vendors_with_numbers.sort(key=lambda x: x[1], reverse=True)
    for vendor, count in vendors_with_numbers[:10]:
        print(f"   '{vendor}' ({count} receipts)")
    if len(vendors_with_numbers) > 10:
        print(f"   ... and {len(vendors_with_numbers) - 10} more")
else:
    print("✅ No receipt numbers found in vendor names")

# 2. Check banking_transactions vendor standardization
print("\n\n2. BANKING TRANSACTIONS VENDOR ANALYSIS")
print("-" * 80)

cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE vendor_extracted IS NOT NULL
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

banking_vendors = {}
internal_transfer_count = 0
for row in cur.fetchall():
    vendor, count, first_date, last_date = row
    if is_internal_transfer(vendor):
        internal_transfer_count += count
    else:
        banking_vendors[vendor] = {
            'count': count,
            'first_date': first_date,
            'last_date': last_date
        }

print(f"Total unique banking vendors (excluding {internal_transfer_count} internal transfers): {len(banking_vendors)}")

# Check for potential duplicates in banking
print("\nChecking for similar vendor names in banking...")
potential_banking_duplicates = []
banking_vendors_list = list(banking_vendors.keys())

for i, vendor1 in enumerate(banking_vendors_list):
    for vendor2 in banking_vendors_list[i+1:]:
        similarity = similar_strings(vendor1, vendor2)
        if 0.85 <= similarity < 1.0:
            count1 = banking_vendors[vendor1]['count']
            count2 = banking_vendors[vendor2]['count']
            potential_banking_duplicates.append({
                'vendor1': vendor1,
                'vendor2': vendor2,
                'similarity': similarity,
                'count1': count1,
                'count2': count2,
                'total': count1 + count2
            })

if potential_banking_duplicates:
    print(f"\n⚠️  Found {len(potential_banking_duplicates)} potential duplicate vendor pairs in banking:")
    potential_banking_duplicates.sort(key=lambda x: x['total'], reverse=True)
    for i, dup in enumerate(potential_banking_duplicates[:20], 1):
        print(f"\n{i}. Similarity: {dup['similarity']:.1%}")
        print(f"   '{dup['vendor1']}' ({dup['count1']} transactions)")
        print(f"   '{dup['vendor2']}' ({dup['count2']} transactions)")
        print(f"   Total impact: {dup['total']} transactions")
    if len(potential_banking_duplicates) > 20:
        print(f"\n   ... and {len(potential_banking_duplicates) - 20} more pairs")
else:
    print("✅ No similar vendor names found in banking")

# 3. Check for NULL/empty vendors
print("\n\n3. NULL/EMPTY VENDOR CHECK")
print("-" * 80)

cur.execute("SELECT COUNT(*) FROM receipts WHERE vendor_name IS NULL OR vendor_name = ''")
null_receipt_vendors = cur.fetchone()[0]
print(f"Receipts with NULL/empty vendor: {null_receipt_vendors}")

cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE vendor_extracted IS NULL OR vendor_extracted = ''")
null_banking_vendors = cur.fetchone()[0]
print(f"Banking transactions with NULL/empty vendor: {null_banking_vendors}")

# 4. Global Payments verification
print("\n\n4. GLOBAL PAYMENTS VERIFICATION")
print("-" * 80)

cur.execute("""
    SELECT 
        vendor_extracted,
        COUNT(*) as count
    FROM banking_transactions
    WHERE description LIKE '%GBL VI%' 
       OR description LIKE '%GBL MC%'
       OR description LIKE '%GBL AX%'
       OR description LIKE '%GLOBAL%VISA%'
       OR description LIKE '%GLOBAL%MASTERCARD%'
       OR description LIKE '%GLOBAL%AMEX%'
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

global_payments = cur.fetchall()
if global_payments:
    print(f"Found {len(global_payments)} Global Payments vendor variations:")
    for vendor, count in global_payments[:10]:
        print(f"   '{vendor}' ({count} transactions)")
else:
    print("✅ All Global Payments vendors standardized")

# 5. Summary
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

issues_found = []

if potential_duplicates:
    issues_found.append(f"⚠️  {len(potential_duplicates)} potential duplicate vendor pairs in receipts")
if vendors_with_numbers:
    issues_found.append(f"⚠️  {len(vendors_with_numbers)} vendors with receipt numbers in receipts")
if potential_banking_duplicates:
    issues_found.append(f"⚠️  {len(potential_banking_duplicates)} potential duplicate vendor pairs in banking")
if null_receipt_vendors > 0:
    issues_found.append(f"⚠️  {null_receipt_vendors} receipts with NULL/empty vendor")
if null_banking_vendors > 0:
    issues_found.append(f"⚠️  {null_banking_vendors} banking transactions with NULL/empty vendor")
if global_payments and len(global_payments) > 3:  # More than expected standardized names
    issues_found.append(f"⚠️  {len(global_payments)} Global Payments vendor variations")

if issues_found:
    print("\nISSUES FOUND:")
    for issue in issues_found:
        print(f"  {issue}")
else:
    print("\n✅ ALL VENDOR NAMES ARE STANDARDIZED")
    print("✅ No duplicates or variations found")
    print("✅ Internal transfers properly excluded")

print(f"\nTotal unique vendors:")
print(f"  Receipts: {len(receipt_vendors)}")
print(f"  Banking: {len(banking_vendors)}")
print(f"  Internal transfers excluded: {internal_transfer_count}")

cur.close()
conn.close()
