#!/usr/bin/env python3
"""
Analyze and standardize vendor names from verified 2012-2014 banking data
All vendors will be uppercase with consistent formatting
"""
import psycopg2
import re
from collections import defaultdict

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*100)
print("VENDOR NAME STANDARDIZATION - 2012-2014 BANKING DATA")
print("="*100)

# Get all vendor names from verified banking 2012-2014
cur.execute("""
    SELECT DISTINCT
        UPPER(TRIM(vendor_extracted)) as vendor_upper,
        COUNT(*) as frequency,
        SUM(COALESCE(debit_amount, credit_amount, 0)) as total_amount
    FROM banking_transactions
    WHERE verified = TRUE
    AND locked = TRUE
    AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
    AND vendor_extracted IS NOT NULL
    AND vendor_extracted != ''
    GROUP BY vendor_upper
    ORDER BY frequency DESC
""")

vendors = cur.fetchall()

print(f"\n📊 Found {len(vendors)} unique vendor names in verified banking (2012-2014)")
print(f"\nTop 50 vendors by transaction frequency:")
print(f"\n{'Vendor Name':<60} {'Count':>8} {'Total Amount':>15}")
print("-"*85)

# Analyze patterns for standardization
vendor_mapping = {}
patterns = {
    'FAS GAS': [],
    'SHELL': [],
    'CO-OP': [],
    'PETRO': [],
    'MCARD': [],
    'VCARD': [],
    'ACARD': [],
    'CAPITAL ONE': [],
    'CHQ': [],
    'EMAIL': [],
    'ATM': [],
    'TRANSFER': [],
    'NSF': [],
    'BANK FEE': [],
    'INSURANCE': [],
    'LEASE': [],
}

for idx, (vendor, count, amount) in enumerate(vendors[:50]):
    vendor_str = vendor[:58] if vendor else ''
    print(f"{vendor_str:<60} {count:>8,} ${amount:>13,.2f}")
    
    # Categorize by pattern
    for pattern_key in patterns.keys():
        if pattern_key in vendor:
            patterns[pattern_key].append(vendor)

# Show pattern analysis
print("\n\n" + "="*100)
print("VENDOR NAME PATTERNS")
print("="*100)

for pattern, vendor_list in patterns.items():
    if vendor_list:
        print(f"\n{pattern} ({len(vendor_list)} variations):")
        for v in sorted(set(vendor_list))[:10]:
            print(f"   - {v}")

# Create standardization rules
standardization_rules = {}

print("\n\n" + "="*100)
print("STANDARDIZATION RULES")
print("="*100)

# FAS GAS standardization
print("\n1. FAS GAS locations:")
cur.execute("""
    SELECT DISTINCT UPPER(TRIM(vendor_extracted)) as vendor
    FROM banking_transactions
    WHERE verified = TRUE
    AND UPPER(vendor_extracted) LIKE '%FAS GAS%'
    ORDER BY vendor
""")
fas_gas_vendors = [row[0] for row in cur.fetchall()]
for idx, vendor in enumerate(fas_gas_vendors[:10]):
    # Extract location number if exists
    match = re.search(r'(?:FAS GAS|FASGAS)\s*(\d+)', vendor)
    if match:
        standardized = f"FAS GAS {match.group(1)}"
    else:
        standardized = "FAS GAS"
    print(f"   {vendor:<50} → {standardized}")
    standardization_rules[vendor] = standardized

# Shell standardization
print("\n2. SHELL locations:")
cur.execute("""
    SELECT DISTINCT UPPER(TRIM(vendor_extracted)) as vendor
    FROM banking_transactions
    WHERE verified = TRUE
    AND UPPER(vendor_extracted) LIKE '%SHELL%'
    ORDER BY vendor
""")
shell_vendors = [row[0] for row in cur.fetchall()]
for vendor in shell_vendors[:10]:
    match = re.search(r'SHELL\s*(\d+)', vendor)
    if match:
        standardized = f"SHELL {match.group(1)}"
    else:
        standardized = "SHELL"
    print(f"   {vendor:<50} → {standardized}")
    standardization_rules[vendor] = standardized

# Card deposits
print("\n3. Card deposits:")
card_patterns = [
    (r'MCARD.*DEPOSIT', 'MCARD DEPOSIT'),
    (r'VCARD.*DEPOSIT', 'VCARD DEPOSIT'),
    (r'ACARD.*DEPOSIT', 'ACARD DEPOSIT'),
]
for pattern, standardized in card_patterns:
    cur.execute(f"""
        SELECT DISTINCT UPPER(TRIM(vendor_extracted)) as vendor
        FROM banking_transactions
        WHERE verified = TRUE
        AND UPPER(vendor_extracted) ~ '{pattern}'
        LIMIT 5
    """)
    for (vendor,) in cur.fetchall():
        print(f"   {vendor:<50} → {standardized}")
        standardization_rules[vendor] = standardized

# Email transfers
print("\n4. Email transfers:")
cur.execute("""
    SELECT DISTINCT UPPER(TRIM(vendor_extracted)) as vendor
    FROM banking_transactions
    WHERE verified = TRUE
    AND UPPER(vendor_extracted) LIKE '%EMAIL%'
    AND UPPER(vendor_extracted) LIKE '%TRANSFER%'
    ORDER BY vendor
    LIMIT 10
""")
for (vendor,) in cur.fetchall():
    if 'FEE' in vendor:
        standardized = 'EMAIL TRANSFER FEE'
    else:
        standardized = 'EMAIL TRANSFER'
    print(f"   {vendor:<50} → {standardized}")
    standardization_rules[vendor] = standardized

# NSF charges
print("\n5. NSF charges:")
cur.execute("""
    SELECT DISTINCT UPPER(TRIM(vendor_extracted)) as vendor
    FROM banking_transactions
    WHERE verified = TRUE
    AND is_nsf_charge = TRUE
    AND vendor_extracted IS NOT NULL
    ORDER BY vendor
    LIMIT 10
""")
for (vendor,) in cur.fetchall():
    if 'FEE' in vendor:
        standardized = 'NSF FEE'
    elif 'RETURNED' in vendor:
        standardized = 'NSF RETURNED ITEM'
    else:
        standardized = 'NSF CHARGE'
    print(f"   {vendor:<50} → {standardized}")
    standardization_rules[vendor] = standardized

# Bank fees
print("\n6. Bank fees:")
fee_keywords = ['BANK FEE', 'SERVICE CHARGE', 'INTERAC FEE', 'ATM FEE']
for keyword in fee_keywords:
    cur.execute(f"""
        SELECT DISTINCT UPPER(TRIM(vendor_extracted)) as vendor
        FROM banking_transactions
        WHERE verified = TRUE
        AND UPPER(vendor_extracted) LIKE '%{keyword}%'
        LIMIT 3
    """)
    for (vendor,) in cur.fetchall():
        if 'INTERAC' in vendor:
            standardized = 'INTERAC FEE'
        elif 'ATM' in vendor:
            standardized = 'ATM FEE'
        elif 'SERVICE' in vendor:
            standardized = 'SERVICE CHARGE'
        else:
            standardized = 'BANK FEE'
        print(f"   {vendor:<50} → {standardized}")
        standardization_rules[vendor] = standardized

print(f"\n\n📊 Total standardization rules created: {len(standardization_rules)}")

# Generate full mapping for all vendors
print("\n\n" + "="*100)
print("GENERATING COMPREHENSIVE VENDOR MAPPING")
print("="*100)

comprehensive_mapping = {}

for vendor, count, amount in vendors:
    if vendor in standardization_rules:
        comprehensive_mapping[vendor] = standardization_rules[vendor]
    else:
        # Default: Just uppercase and trim
        comprehensive_mapping[vendor] = vendor.upper().strip()

# Save to file
import json
output_file = 'l:\\limo\\data\\vendor_standardization_mapping.json'
with open(output_file, 'w') as f:
    json.dump({
        'mapping': comprehensive_mapping,
        'rules': {
            'source': 'Banking transactions 2012-2014 (verified/locked)',
            'total_vendors': len(comprehensive_mapping),
            'standardized_count': len(standardization_rules),
            'format': 'ALL UPPERCASE'
        }
    }, f, indent=2)

print(f"\n✅ Saved comprehensive mapping to: {output_file}")
print(f"   Total vendors: {len(comprehensive_mapping)}")
print(f"   With standardization: {len(standardization_rules)}")
print(f"   Format: ALL UPPERCASE")

cur.close()
conn.close()
