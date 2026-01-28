#!/usr/bin/env python
"""
Comprehensive analysis of 2019 split receipts
Identify all edge cases, data quality issues, and validation rules needed
"""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect('host=localhost user=postgres password=***REMOVED*** dbname=almsdata')
cur = conn.cursor()

print("="*80)
print("COMPREHENSIVE 2019 SPLIT RECEIPT ANALYSIS")
print("="*80)

# Get all 2019 splits with description patterns
cur.execute("""
SELECT 
    receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gst_code,
    description, gl_account_code, payment_method, sales_tax, tax_category
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date) = 2019
AND description LIKE '%SPLIT%'
ORDER BY description, receipt_id
""")

rows = cur.fetchall()
print(f"\n1. TOTAL 2019 SPLITS FOUND: {len(rows)} receipts\n")

# Group by SPLIT/ tag to analyze groups
split_groups = defaultdict(list)
for row in rows:
    receipt_id, date, vendor, gross, gst, gst_code, desc, gl, payment, pst, tax_cat = row
    
    # Extract SPLIT/<amount> from description
    if 'SPLIT' in desc:
        parts = desc.split('SPLIT/')
        if len(parts) > 1:
            split_amount = parts[1].split()[0].strip()
        else:
            split_amount = "UNKNOWN"
    else:
        split_amount = "UNKNOWN"
    
    split_groups[split_amount].append({
        'receipt_id': receipt_id,
        'date': date,
        'vendor': vendor,
        'gross': float(gross),
        'gst': float(gst),
        'gst_code': gst_code,
        'desc': desc,
        'gl': gl,
        'payment': payment,
        'pst': float(pst or 0),
        'tax_cat': tax_cat
    })

print(f"2. SPLIT GROUPS: {len(split_groups)} unique SPLIT/ tags\n")

# Analyze each group
issues = {
    'mismatched_totals': [],
    'duplicate_totals': [],
    'zero_gst_items': [],
    'mixed_gst_in_group': [],
    'payment_method_variants': [],
    'gl_code_variants': [],
    'vendor_spelling': []
}

for split_tag, receipts in sorted(split_groups.items()):
    if len(receipts) < 2:
        continue  # Skip single receipts
    
    # Parse the target total from SPLIT tag
    try:
        target_total = float(split_tag.rstrip('CAD').strip())
    except:
        target_total = None
    
    # Sum actual receipts
    actual_total = sum(r['gross'] for r in receipts)
    
    print(f"\nSPLIT/{split_tag}")
    print(f"  Group size: {len(receipts)} receipts")
    print(f"  Target: ${target_total:.2f}" if target_total else "  Target: UNKNOWN")
    print(f"  Actual: ${actual_total:.2f}")
    
    # Check for mismatches
    if target_total and abs(actual_total - target_total) > 0.01:
        print(f"  ❌ MISMATCH: ${abs(actual_total - target_total):.2f} difference")
        issues['mismatched_totals'].append({
            'split_tag': split_tag,
            'target': target_total,
            'actual': actual_total,
            'receipts': receipts
        })
    else:
        print(f"  ✅ Totals match")
    
    # List receipts in group
    for i, r in enumerate(receipts, 1):
        gst_display = f"${r['gst']:.2f}" if r['gst'] > 0 else "$0.00 (no GST)"
        print(f"    {i}. Rcpt#{r['receipt_id']}: ${r['gross']:.2f} | GST {gst_display} | GL {r['gl']} | {r['payment']} | {r['desc'][:50]}")
    
    # Check for zero GST items
    zero_gst = [r for r in receipts if r['gst'] == 0 or r['gst'] is None]
    if zero_gst:
        print(f"  ⚠️  {len(zero_gst)} receipt(s) with NO GST:")
        for r in zero_gst:
            print(f"      Rcpt#{r['receipt_id']}: {r['desc'][:60]}")
            issues['zero_gst_items'].append({'split_tag': split_tag, 'receipt': r})
    
    # Check for mixed GST codes in group
    gst_codes = set(r['gst_code'] for r in receipts if r['gst_code'])
    if len(gst_codes) > 1:
        print(f"  ⚠️  MIXED GST CODES in group: {gst_codes}")
        issues['mixed_gst_in_group'].append({'split_tag': split_tag, 'codes': gst_codes})
    
    # Check for payment method variants
    payment_methods = set(r['payment'] for r in receipts if r['payment'])
    if len(payment_methods) > 1:
        print(f"  ℹ️  Multiple payment methods: {payment_methods}")
        issues['payment_method_variants'].append({'split_tag': split_tag, 'methods': payment_methods})
    
    # Check for GL code variants
    gl_codes = set(r['gl'] for r in receipts if r['gl'])
    if len(gl_codes) > 1:
        print(f"  ℹ️  Multiple GL codes: {gl_codes}")
        issues['gl_code_variants'].append({'split_tag': split_tag, 'gls': gl_codes})

# Find duplicate totals (different SPLIT tags with same amount)
print("\n" + "="*80)
print("3. DATA QUALITY ISSUES SUMMARY")
print("="*80)

# Totals histogram
total_counts = defaultdict(int)
for split_tag in split_groups.keys():
    try:
        total = float(split_tag.rstrip('CAD').strip())
        total_counts[total] += 1
    except:
        pass

duplicates = {amt: cnt for amt, cnt in total_counts.items() if cnt > 1}
if duplicates:
    print(f"\n⚠️  DUPLICATE TOTALS ({len(duplicates)} amounts appear multiple times):")
    for amt, cnt in sorted(duplicates.items(), reverse=True):
        print(f"   ${amt:.2f} appears {cnt} times")
        # Find which split tags
        matching_tags = [tag for tag in split_groups.keys() if tag.rstrip('CAD').strip() and float(tag.rstrip('CAD').strip()) == amt]
        for tag in matching_tags:
            receipts = split_groups[tag]
            print(f"      • {tag}: {len(receipts)} receipts, vendors: {', '.join(set(r['vendor'] for r in receipts))}")
        issues['duplicate_totals'].append({'amount': amt, 'count': cnt})

# Summary of issues
print(f"\n⚠️  ISSUE SUMMARY:")
print(f"   Mismatched totals: {len(issues['mismatched_totals'])}")
print(f"   Zero-GST items: {len(issues['zero_gst_items'])}")
print(f"   Mixed GST codes in groups: {len(issues['mixed_gst_in_group'])}")
print(f"   Multiple payment methods: {len(issues['payment_method_variants'])}")
print(f"   Multiple GL codes: {len(issues['gl_code_variants'])}")
print(f"   Duplicate total amounts: {len(issues['duplicate_totals'])}")

# Detailed issue reports
if issues['mismatched_totals']:
    print(f"\n" + "="*80)
    print("MISMATCHED TOTALS (receipts don't sum to SPLIT/ tag)")
    print("="*80)
    for issue in issues['mismatched_totals']:
        print(f"\nSPLIT/{issue['split_tag']}")
        print(f"  Target: ${issue['target']:.2f}")
        print(f"  Actual: ${issue['actual']:.2f}")
        print(f"  Difference: ${abs(issue['actual'] - issue['target']):.2f}")
        print(f"  Receipts:")
        for r in issue['receipts']:
            print(f"    Rcpt#{r['receipt_id']}: ${r['gross']:.2f} - {r['desc']}")

if issues['zero_gst_items']:
    print(f"\n" + "="*80)
    print("ZERO-GST ITEMS (e.g., ICE, WATER, LITRELOG PAYMENT)")
    print("="*80)
    for issue in issues['zero_gst_items']:
        r = issue['receipt']
        print(f"\nSPLIT/{issue['split_tag']}")
        print(f"  Rcpt#{r['receipt_id']}: ${r['gross']:.2f}")
        print(f"  Description: {r['desc']}")
        print(f"  GL: {r['gl']}")
        print(f"  Payment: {r['payment']}")
        print(f"  GST Code: {r['gst_code']}")

if issues['payment_method_variants']:
    print(f"\n" + "="*80)
    print("MULTI-PAYMENT GROUPS (different payment methods in same SPLIT/)")
    print("="*80)
    for issue in issues['payment_method_variants']:
        print(f"\nSPLIT/{issue['split_tag']}")
        print(f"  Payment methods: {issue['methods']}")
        group = split_groups[issue['split_tag']]
        for r in group:
            print(f"    {r['payment']}: Rcpt#{r['receipt_id']} ${r['gross']:.2f}")

if issues['gl_code_variants']:
    print(f"\n" + "="*80)
    print("MULTI-GL GROUPS (different GL codes in same SPLIT/)")
    print("="*80)
    for issue in issues['gl_code_variants']:
        print(f"\nSPLIT/{issue['split_tag']}")
        print(f"  GL codes: {issue['gls']}")
        group = split_groups[issue['split_tag']]
        for r in group:
            print(f"    GL {r['gl']}: Rcpt#{r['receipt_id']} ${r['gross']:.2f} - {r['desc'][:50]}")

# Validation rules for our implementation
print(f"\n" + "="*80)
print("4. VALIDATION RULES FOR SPLIT RECEIPT IMPLEMENTATION")
print("="*80)

print("""
✅ REQUIRED VALIDATION:
   1. Sum of split grosses must equal original banking amount (±$0.01)
   2. Each split must have GL code (cannot be NULL)
   3. Each split must have payment method (cannot be NULL)
   4. All splits must share same SPLIT/<amount> tag in description
   5. GST calculation: line_gst = gross * 0.05 / 1.05 (if GST_INCL_5)
   6. GST calculation: line_gst = 0 if gst_code is NULL or non-standard
   
✅ EDGE CASES TO HANDLE:
   1. Zero-GST items (Ice, Water, Litrelog Payment rebates)
      → Allow gst_code = NULL or empty, set gst_amount = 0
   2. Multiple payment methods in one SPLIT/
      → Each receipt records its own payment method (OK - our design)
   3. Multiple GL codes in one SPLIT/
      → Each receipt records its own GL code (OK - our design)
   4. Duplicate total amounts
      → Use SPLIT/<amount> tag + date + vendor to identify group (OK - our design)
   5. Litrelog payments (negative or rebate-style entries)
      → Treat as normal line item with GL code, $0 GST
   
✅ DATA QUALITY NOTES:
   - Some 2019 entries may have typos/inconsistencies
   - Our "Divide by Payment Methods" dialog will create CLEAN splits
   - Existing 2019 splits are READ-ONLY for audit purposes
   - New splits created via dialog follow strict validation rules
""")

cur.close()
conn.close()

print("\n" + "="*80)
print("END OF ANALYSIS")
print("="*80)
