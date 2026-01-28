#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
find_vendor_name_variations.py

Identify vendor name variations that could be combined under standardized naming.
Groups similar vendor names by pattern matching to find duplicates.
"""

import psycopg2
import re
from collections import defaultdict
from difflib import SequenceMatcher

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def normalize_for_comparison(vendor):
    """Normalize vendor name for similarity comparison."""
    if not vendor:
        return ""
    
    # Remove common suffixes/prefixes
    normalized = vendor.upper()
    normalized = re.sub(r'\s+(LTD|INC|CORP|CO|LLC|CANADA|CANADIAN)\b', '', normalized)
    normalized = re.sub(r'\b(THE)\s+', '', normalized)
    
    # Remove punctuation
    normalized = re.sub(r'[^\w\s]', '', normalized)
    
    # Remove extra whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized

def extract_base_name(vendor):
    """Extract base vendor name without numbers/locations."""
    if not vendor:
        return ""
    
    # Remove trailing numbers
    base = re.sub(r'\s+\d+$', '', vendor)
    
    # Remove location indicators
    base = re.sub(r'\s+(CALGARY|EDMONTON|ALBERTA|AB)\b', '', base, flags=re.IGNORECASE)
    
    return base.strip()

def similarity_ratio(a, b):
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

print("\n" + "="*110)
print("VENDOR NAME VARIATION ANALYSIS")
print("="*110 + "\n")

# Get all vendor names from banking
print("Collecting vendor names from banking_transactions...")
cur.execute("""
    SELECT vendor_extracted, COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions
    WHERE vendor_extracted IS NOT NULL
    AND verified = TRUE
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

banking_vendors = {}
for vendor, count, debits, credits in cur.fetchall():
    banking_vendors[vendor] = {
        'count': count,
        'debits': debits or 0,
        'credits': credits or 0,
        'source': 'banking'
    }

# Get all vendor names from receipts
print("Collecting vendor names from receipts...")
cur.execute("""
    SELECT vendor_name, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name IS NOT NULL
    GROUP BY vendor_name
    ORDER BY COUNT(*) DESC
""")

receipt_vendors = {}
for vendor, count, total in cur.fetchall():
    receipt_vendors[vendor] = {
        'count': count,
        'total': total or 0,
        'source': 'receipts'
    }

# Combine all vendors
all_vendors = {}
for vendor, data in banking_vendors.items():
    all_vendors[vendor] = data

for vendor, data in receipt_vendors.items():
    if vendor in all_vendors:
        all_vendors[vendor]['count'] += data['count']
        all_vendors[vendor]['source'] = 'both'
    else:
        all_vendors[vendor] = data

print(f"Found {len(all_vendors)} unique vendor names\n")

# Group by base name patterns
base_groups = defaultdict(list)
for vendor in all_vendors.keys():
    base = extract_base_name(vendor)
    if base:
        base_groups[base.upper()].append(vendor)

# Find groups with variations
variation_groups = []
for base, variants in base_groups.items():
    if len(variants) > 1:
        # Calculate total transactions
        total_count = sum(all_vendors[v]['count'] for v in variants)
        variation_groups.append({
            'base': base,
            'variants': sorted(variants, key=lambda v: all_vendors[v]['count'], reverse=True),
            'total_count': total_count
        })

# Sort by total transaction count
variation_groups.sort(key=lambda g: g['total_count'], reverse=True)

print("="*110)
print(f"VENDOR GROUPS WITH VARIATIONS (Top 50 by transaction count)")
print("="*110 + "\n")

shown = 0
for group in variation_groups[:50]:
    base = group['base']
    variants = group['variants']
    total = group['total_count']
    
    print(f"\n{'='*110}")
    print(f"BASE: {base} ({total:,} total transactions)")
    print(f"{'='*110}")
    
    for variant in variants:
        data = all_vendors[variant]
        count = data['count']
        source = data['source']
        
        if 'debits' in data:
            debits = data['debits']
            credits = data['credits']
            print(f"  {variant:<60} {count:>6} tx | D: ${debits:>12,.2f} | C: ${credits:>12,.2f} | {source}")
        else:
            total_amt = data['total']
            print(f"  {variant:<60} {count:>6} tx | Total: ${total_amt:>12,.2f} | {source}")
    
    shown += 1

if len(variation_groups) > 50:
    print(f"\n... and {len(variation_groups) - 50} more vendor groups")

print("\n" + "="*110)
print("SIMILAR NAME PATTERNS (Fuzzy Matching)")
print("="*110 + "\n")

# Find similar names that aren't in the same base group
similar_pairs = []
vendor_list = list(all_vendors.keys())

print("Analyzing name similarities...")

for i, vendor1 in enumerate(vendor_list):
    if i % 100 == 0:
        print(f"   Progress: {i}/{len(vendor_list)}")
    
    norm1 = normalize_for_comparison(vendor1)
    if not norm1 or len(norm1) < 4:
        continue
    
    for vendor2 in vendor_list[i+1:]:
        norm2 = normalize_for_comparison(vendor2)
        if not norm2 or len(norm2) < 4:
            continue
        
        # Skip if already in same base group
        base1 = extract_base_name(vendor1).upper()
        base2 = extract_base_name(vendor2).upper()
        if base1 == base2:
            continue
        
        # Calculate similarity
        ratio = similarity_ratio(norm1, norm2)
        
        if ratio >= 0.75:  # 75% similar
            count1 = all_vendors[vendor1]['count']
            count2 = all_vendors[vendor2]['count']
            similar_pairs.append({
                'vendor1': vendor1,
                'vendor2': vendor2,
                'ratio': ratio,
                'total_count': count1 + count2
            })

# Sort by similarity and transaction count
similar_pairs.sort(key=lambda p: (p['ratio'], p['total_count']), reverse=True)

print(f"\nFound {len(similar_pairs)} similar vendor pairs\n")

shown = 0
for pair in similar_pairs[:30]:
    if shown == 0:
        print(f"{'Vendor 1':<45} {'Vendor 2':<45} {'Similarity':>10} {'Transactions':>12}")
        print("-"*110)
    
    v1 = pair['vendor1']
    v2 = pair['vendor2']
    ratio = pair['ratio']
    total = pair['total_count']
    
    print(f"{v1:<45} {v2:<45} {ratio:>9.1%} {total:>12,}")
    shown += 1

if len(similar_pairs) > 30:
    print(f"... and {len(similar_pairs) - 30} more similar pairs")

print("\n" + "="*110)
print("SUGGESTED STANDARDIZATIONS")
print("="*110 + "\n")

# Generate standardization suggestions
suggestions = []

# Common patterns to standardize
patterns = {
    r'^(FAS\s*GAS|FASGAS)': 'FAS GAS',
    r'^(SHELL|SHELL\s+CANADA)': 'SHELL',
    r'^(CO[\s-]?OP|COOP)(?!\s+INSURANCE)': 'CO-OP',
    r'^(PETRO\s*CANADA|PETROCAN)': 'PETRO CANADA',
    r'^(TIM\s*HORTONS?|TIMHORTONS)': 'TIM HORTONS',
    r'^(CANADIAN\s*TIRE|CDN\s*TIRE)': 'CANADIAN TIRE',
    r'^(HUSKY|HUSKY\s+ENERGY)': 'HUSKY',
    r'^(ESSO|ESSO\s+CANADA)': 'ESSO',
    r'^(COSTCO|COSTCO\s+WHOLESALE)': 'COSTCO',
    r'^(WAL[\s-]?MART|WALMART)': 'WALMART',
    r'^(7[\s-]?ELEVEN|7ELEVEN)': '7-ELEVEN',
    r'^(SAFEWAY|SAFEWAY\s+CANADA)': 'SAFEWAY',
    r'^(SUPERSTORE|REAL\s+CANADIAN\s+SUPERSTORE)': 'SUPERSTORE',
}

for vendor, data in all_vendors.items():
    for pattern, standard in patterns.items():
        if re.match(pattern, vendor, re.IGNORECASE):
            # Keep numbered locations
            match = re.search(r'\s+(\d+)$', vendor)
            if match:
                suggested = f"{standard} {match.group(1)}"
            else:
                suggested = standard
            
            if vendor != suggested:
                suggestions.append({
                    'original': vendor,
                    'suggested': suggested,
                    'count': data['count'],
                    'pattern': pattern
                })
                break

# Sort by transaction count
suggestions.sort(key=lambda s: s['count'], reverse=True)

if suggestions:
    print(f"{'Original':<50} {'Suggested':<50} {'Transactions':>10}")
    print("-"*110)
    
    for sug in suggestions[:50]:
        print(f"{sug['original']:<50} {sug['suggested']:<50} {sug['count']:>10,}")
    
    if len(suggestions) > 50:
        print(f"\n... and {len(suggestions) - 50} more suggestions")
    
    print(f"\nTotal standardization opportunities: {len(suggestions)}")
else:
    print("No additional standardization needed based on common patterns")

cur.close()
conn.close()

print("\n" + "="*110)
print("ANALYSIS COMPLETE")
print("="*110)
