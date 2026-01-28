#!/usr/bin/env python
"""
Receipt deduplication verification using fuzzy vendor matching + amount + date range.
Identifies potential duplicate receipts for manual review.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from difflib import SequenceMatcher
from collections import defaultdict
from datetime import timedelta, datetime
import csv

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 120)
print("RECEIPT DEDUPLICATION VERIFICATION")
print("=" * 120)

def normalize_vendor(vendor_name):
    """Normalize vendor name for fuzzy matching."""
    if not vendor_name:
        return ""
    
    vendor = vendor_name.upper().strip()
    
    # Remove common suffixes and prefixes
    vendor = vendor.replace("'S", "")
    vendor = vendor.replace("'", "")
    
    # Remove common company suffixes
    for suffix in [' INC', ' CORP', ' LTD', ' LIMITED', ' LLC', ' COMPANY', ' CO']:
        if vendor.endswith(suffix):
            vendor = vendor[:-len(suffix)].strip()
    
    # Normalize common chains
    replacements = {
        'TIM HORTON': 'TIM HORTONS',
        'CANADIAN TIRE': 'CANADIAN TIRE',
        'COSTCO': 'COSTCO',
        'STAPLES': 'STAPLES',
        'BEST BUY': 'BEST BUY',
        'FUTURE SHOP': 'FUTURE SHOP',
    }
    
    for old, new in replacements.items():
        if old in vendor:
            vendor = new
    
    return vendor

def fuzzy_match_vendor(vendor1, vendor2, threshold=0.85):
    """
    Calculate fuzzy match ratio between two vendor names.
    Returns (is_match, ratio).
    """
    norm1 = normalize_vendor(vendor1)
    norm2 = normalize_vendor(vendor2)
    
    if not norm1 or not norm2:
        return False, 0.0
    
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    return ratio >= threshold, ratio

def amount_matches(amt1, amt2, tolerance_percent=1.0):
    """
    Check if amounts match within tolerance (default 1%).
    """
    if amt1 == 0 or amt2 == 0:
        return False
    
    diff_percent = abs(amt1 - amt2) / max(abs(amt1), abs(amt2)) * 100
    return diff_percent <= tolerance_percent

print("\n1. LOADING RECEIPTS...")
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description,
        created_from_banking
    FROM receipts
    WHERE vendor_name IS NOT NULL
    AND vendor_name != ''
    ORDER BY vendor_name, receipt_date
""")

receipts = cur.fetchall()
print(f"   Loaded {len(receipts):,} receipts")

# Group by normalized vendor for faster comparison
print("\n2. GROUPING BY VENDOR...")
vendor_groups = defaultdict(list)

for receipt in receipts:
    norm_vendor = normalize_vendor(receipt['vendor_name'])
    vendor_groups[norm_vendor].append(receipt)

print(f"   Found {len(vendor_groups):,} unique vendors")

# Find potential duplicates
print("\n3. SEARCHING FOR DUPLICATES...")
duplicates = []
checked_pairs = set()

for norm_vendor, receipts_in_group in vendor_groups.items():
    if len(receipts_in_group) < 2:
        continue
    
    # Sort by date for easier comparison
    receipts_in_group = sorted(receipts_in_group, key=lambda r: r['receipt_date'])
    
    # Check each pair within group
    for i in range(len(receipts_in_group)):
        for j in range(i + 1, len(receipts_in_group)):
            rec1 = receipts_in_group[i]
            rec2 = receipts_in_group[j]
            
            # Skip if already checked (avoid duplicate comparisons)
            pair_key = tuple(sorted([rec1['receipt_id'], rec2['receipt_id']]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)
            
            # Check vendor fuzzy match
            is_vendor_match, vendor_ratio = fuzzy_match_vendor(
                rec1['vendor_name'], 
                rec2['vendor_name'],
                threshold=0.80  # Lower threshold for cross-group matches
            )
            
            if not is_vendor_match:
                continue
            
            # Check amount match (within 2%)
            if not amount_matches(float(rec1['gross_amount']), float(rec2['gross_amount']), tolerance_percent=2.0):
                continue
            
            # Check date range (within 14 days)
            date_diff = abs((rec2['receipt_date'] - rec1['receipt_date']).days)
            if date_diff > 14:
                continue
            
            # This is a potential duplicate
            duplicates.append({
                'receipt_1': rec1['receipt_id'],
                'date_1': rec1['receipt_date'],
                'vendor_1': rec1['vendor_name'],
                'amount_1': float(rec1['gross_amount']),
                'banking_1': rec1['created_from_banking'],
                'receipt_2': rec2['receipt_id'],
                'date_2': rec2['receipt_date'],
                'vendor_2': rec2['vendor_name'],
                'amount_2': float(rec2['gross_amount']),
                'banking_2': rec2['created_from_banking'],
                'vendor_ratio': vendor_ratio,
                'date_diff': date_diff,
                'amount_diff_pct': abs(float(rec1['gross_amount']) - float(rec2['gross_amount'])) / max(float(rec1['gross_amount']), float(rec2['gross_amount'])) * 100,
            })

print(f"   Found {len(duplicates):,} potential duplicate pairs")

# Categorize duplicates
print("\n" + "=" * 120)
print("DUPLICATE ANALYSIS")
print("=" * 120)

# Category 1: Both from banking (likely TRUE duplicates)
both_banking = [d for d in duplicates if d['banking_1'] and d['banking_2']]
print(f"\n1. BOTH FROM BANKING IMPORT (TRUE DUPLICATES): {len(both_banking)}")
if both_banking:
    for dup in sorted(both_banking, key=lambda d: d['amount_1'], reverse=True)[:20]:
        print(f"   Receipts {dup['receipt_1']} & {dup['receipt_2']}")
        print(f"     Vendor: {dup['vendor_1'][:40]} (match: {dup['vendor_ratio']:.0%})")
        print(f"     Amount: ${dup['amount_1']:,.2f} vs ${dup['amount_2']:,.2f} (diff: {dup['amount_diff_pct']:.1f}%)")
        print(f"     Date: {dup['date_1']} vs {dup['date_2']} ({dup['date_diff']} days apart)")
        print()

# Category 2: One from banking, one not (likely same transaction from different sources)
mixed_banking = [d for d in duplicates if d['banking_1'] != d['banking_2']]
print(f"\n2. MIXED SOURCES (BANKING + MANUAL): {len(mixed_banking)}")
if mixed_banking:
    for dup in sorted(mixed_banking, key=lambda d: d['amount_1'], reverse=True)[:20]:
        source_txt = "Banking + Manual"
        print(f"   Receipts {dup['receipt_1']} & {dup['receipt_2']}")
        print(f"     Vendor: {dup['vendor_1'][:40]} (match: {dup['vendor_ratio']:.0%})")
        print(f"     Amount: ${dup['amount_1']:,.2f} vs ${dup['amount_2']:,.2f} (diff: {dup['amount_diff_pct']:.1f}%)")
        print(f"     Date: {dup['date_1']} vs {dup['date_2']} ({dup['date_diff']} days apart)")
        print()

# Category 3: Neither from banking (likely legitimate duplicates - recurring)
neither_banking = [d for d in duplicates if not d['banking_1'] and not d['banking_2']]
print(f"\n3. NEITHER FROM BANKING (MANUAL IMPORTS): {len(neither_banking)}")
if neither_banking:
    for dup in sorted(neither_banking, key=lambda d: d['amount_1'], reverse=True)[:20]:
        print(f"   Receipts {dup['receipt_1']} & {dup['receipt_2']}")
        print(f"     Vendor: {dup['vendor_1'][:40]} (match: {dup['vendor_ratio']:.0%})")
        print(f"     Amount: ${dup['amount_1']:,.2f} vs ${dup['amount_2']:,.2f} (diff: {dup['amount_diff_pct']:.1f}%)")
        print(f"     Date: {dup['date_1']} vs {dup['date_2']} ({dup['date_diff']} days apart)")
        print()

# Summary statistics
print("\n" + "=" * 120)
print("SUMMARY STATISTICS")
print("=" * 120)

print(f"\nTotal receipts analyzed: {len(receipts):,}")
print(f"Unique vendors: {len(vendor_groups):,}")
print(f"Potential duplicate pairs: {len(duplicates):,}")

# Estimate impact
if both_banking:
    both_amount = sum(d['amount_2'] for d in both_banking)  # Use second receipt amount
    print(f"\nEstimated duplicate amount (Banking+Banking): ${both_amount:,.2f} ({len(both_banking)} pairs)")

if mixed_banking:
    mixed_amount = sum(d['amount_2'] for d in mixed_banking if not d['banking_2'])  # Manual entries
    print(f"Estimated duplicate amount (Mixed sources): ${mixed_amount:,.2f} ({len(mixed_banking)} pairs)")

if neither_banking:
    neither_amount = sum(d['amount_2'] for d in neither_banking)
    print(f"Estimated duplicate amount (Manual+Manual): ${neither_amount:,.2f} ({len(neither_banking)} pairs)")

# Quality metrics
print(f"\nDuplicate rate: {len(duplicates)/len(receipts)*100:.2f}% of receipts")
print(f"Duplicate pairs per vendor: {len(duplicates)/max(1, len(vendor_groups)):.2f}")

# Recommendations
print("\n" + "=" * 120)
print("RECOMMENDATIONS")
print("=" * 120)

if both_banking:
    print(f"\n⚠️  HIGH PRIORITY: {len(both_banking)} TRUE DUPLICATES (both from banking)")
    print("   → These should be consolidated/deleted to avoid double-counting")
    print("   → Delete older/duplicate banking imports, keep most recent")

if mixed_banking:
    print(f"\n⚠️  MEDIUM PRIORITY: {len(mixed_banking)} MIXED SOURCE PAIRS")
    print("   → Likely same transaction from different import sources")
    print("   → Verify receipt is correctly linked to banking")
    print("   → Keep manual receipt if provides better detail")

if neither_banking:
    print(f"\n✓  LOW PRIORITY: {len(neither_banking)} MANUAL DUPLICATES")
    print("   → Likely recurring payments (rent, utilities, subscriptions)")
    print("   → Only delete if truly duplicate; verify business need first")

# Export detailed CSV for review
print(f"\n" + "=" * 120)
print("EXPORTING DUPLICATES FOR MANUAL REVIEW")
print("=" * 120)

csv_file = f"l:\\limo\\reports\\receipt_duplicates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        'receipt_1', 'receipt_2', 'vendor_1', 'vendor_2', 'vendor_match_%',
        'date_1', 'date_2', 'date_diff_days',
        'amount_1', 'amount_2', 'amount_diff_%',
        'from_banking_1', 'from_banking_2', 'category'
    ])
    
    for dup in sorted(duplicates, key=lambda d: (
        0 if d['banking_1'] and d['banking_2'] else (1 if d['banking_1'] != d['banking_2'] else 2),
        -d['amount_1']
    )):
        category = 'BOTH_BANKING' if dup['banking_1'] and dup['banking_2'] else (
            'MIXED' if dup['banking_1'] != dup['banking_2'] else 'BOTH_MANUAL'
        )
        
        writer.writerow([
            dup['receipt_1'],
            dup['receipt_2'],
            dup['vendor_1'],
            dup['vendor_2'],
            f"{dup['vendor_ratio']:.0%}",
            dup['date_1'],
            dup['date_2'],
            dup['date_diff'],
            f"${dup['amount_1']:,.2f}",
            f"${dup['amount_2']:,.2f}",
            f"{dup['amount_diff_pct']:.1f}%",
            dup['banking_1'],
            dup['banking_2'],
            category,
        ])

print(f"\n✓ Exported to: {csv_file}")
print(f"  Contains {len(duplicates)} duplicate pairs sorted by priority")

print("\n" + "=" * 120)
print("✓ VERIFICATION COMPLETE")
print("=" * 120 + "\n")

conn.close()
