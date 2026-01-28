#!/usr/bin/env python3
"""
Identify vendor name patterns that need standardization.
Focus on BASE vendor names with variations in suffixes/codes/numbers.
NOT about combining duplicates - just cleaning vendor names.
"""

import psycopg2
import re
from collections import defaultdict

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

print("=" * 80)
print("VENDOR NAME PATTERN ANALYSIS FOR STANDARDIZATION")
print("=" * 80)

def extract_base_vendor_name(vendor):
    """Extract base vendor name by removing common suffixes."""
    if not vendor:
        return None
    
    # Remove common patterns
    cleaned = vendor
    
    # Remove card last 4 digits pattern
    cleaned = re.sub(r'\s+\d{4}\*+\d{3,4}$', '', cleaned)
    
    # Remove transaction IDs (6+ digits at end)
    cleaned = re.sub(r'\s+\d{6,}$', '', cleaned)
    
    # Remove location codes (4-char alphanumeric like 2D54, 1E0U)
    cleaned = re.sub(r'\s+[0-9A-Z]{4}\s+', ' ', cleaned)
    
    # Remove terminal numbers (00339, 7839, etc at end)
    cleaned = re.sub(r'\s+\d{3,5}$', '', cleaned)
    
    # Remove single digit/letter at end
    cleaned = re.sub(r'\s+\d{1}$', '', cleaned)
    cleaned = re.sub(r'\s+[A-Z]{1}$', '', cleaned)
    
    return cleaned.strip()

# Analyze receipts
print("\n1. RECEIPTS VENDOR NAME PATTERNS")
print("-" * 80)

cur = conn.cursor()
cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")

receipt_patterns = defaultdict(list)
for vendor, count in cur.fetchall():
    base = extract_base_vendor_name(vendor)
    if base and base != vendor:  # Only if we extracted something
        receipt_patterns[base].append((vendor, count))

# Find patterns with multiple variations
print(f"\nFound {len(receipt_patterns)} base vendor patterns in receipts")
print("\nTop patterns needing standardization:\n")

# Sort by total transaction count
pattern_totals = []
for base, variations in receipt_patterns.items():
    if len(variations) > 1:  # Multiple variations
        total = sum(count for _, count in variations)
        pattern_totals.append((base, variations, total))

pattern_totals.sort(key=lambda x: x[2], reverse=True)

for i, (base, variations, total) in enumerate(pattern_totals[:30], 1):
    print(f"{i}. BASE: '{base}'")
    print(f"   Total transactions: {total} across {len(variations)} variations")
    # Show top 5 variations
    variations.sort(key=lambda x: x[1], reverse=True)
    for vendor, count in variations[:5]:
        print(f"      '{vendor}' ({count} receipts)")
    if len(variations) > 5:
        print(f"      ... and {len(variations) - 5} more variations")
    print()

# Analyze banking
print("\n2. BANKING VENDOR NAME PATTERNS")
print("-" * 80)

cur.execute("""
    SELECT vendor_extracted, COUNT(*) as count
    FROM banking_transactions
    WHERE vendor_extracted IS NOT NULL
    AND vendor_extracted != ''
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

banking_patterns = defaultdict(list)
for vendor, count in cur.fetchall():
    base = extract_base_vendor_name(vendor)
    if base and base != vendor:
        banking_patterns[base].append((vendor, count))

print(f"\nFound {len(banking_patterns)} base vendor patterns in banking")
print("\nPatterns needing standardization:\n")

banking_totals = []
for base, variations in banking_patterns.items():
    if len(variations) > 1:
        total = sum(count for _, count in variations)
        banking_totals.append((base, variations, total))

banking_totals.sort(key=lambda x: x[2], reverse=True)

for i, (base, variations, total) in enumerate(banking_totals[:20], 1):
    print(f"{i}. BASE: '{base}'")
    print(f"   Total transactions: {total} across {len(variations)} variations")
    variations.sort(key=lambda x: x[1], reverse=True)
    for vendor, count in variations:
        print(f"      '{vendor}' ({count} transactions)")
    print()

# Special analysis: Common prefixes
print("\n3. COMMON VENDOR NAME PREFIXES")
print("-" * 80)

prefix_groups = defaultdict(list)
cur.execute("""
    SELECT vendor_name, COUNT(*) as count
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
""")

for vendor, count in cur.fetchall():
    # Extract first 20 characters as potential prefix
    if len(vendor) > 20:
        prefix = vendor[:20]
        prefix_groups[prefix].append((vendor, count))

print("\nVendor name prefixes with multiple variations:\n")
for prefix, variations in sorted(prefix_groups.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
    if len(variations) > 5:  # Only show if 5+ variations
        total = sum(count for _, count in variations)
        print(f"PREFIX: '{prefix}...'")
        print(f"  {len(variations)} variations, {total} total receipts")
        variations.sort(key=lambda x: x[1], reverse=True)
        for vendor, count in variations[:3]:
            print(f"    '{vendor}' ({count})")
        print()

# Summary
print("\n" + "=" * 80)
print("STANDARDIZATION RECOMMENDATIONS")
print("=" * 80)

print("\n1. ATM/ABM withdrawals - standardize to 'ATM WITHDRAWAL'")
print("   Remove location codes, transaction IDs, card numbers")

print("\n2. Global Payments - remove terminal numbers")
print("   'GLOBAL VISA DEPOSIT 00339' → 'GLOBAL VISA DEPOSIT'")

print("\n3. Point of Sale transactions - clean transaction IDs")
print("   Remove embedded numbers, keep base vendor")

print("\n4. Email transfers - standardize to 'EMAIL TRANSFER'")
print("   Remove fee variations")

print("\n5. Store locations - standardize to base chain name")
print("   Remove store numbers, addresses, etc.")

cur.close()
conn.close()
