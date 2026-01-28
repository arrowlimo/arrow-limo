import psycopg2
import os
import re
from collections import defaultdict

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("ANALYZING ALL SPLIT RECEIPTS IN 2012 AND 2019")
print("=" * 100)

# Find receipts with SPLIT/ or [SPLIT with] pattern
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) IN (2012, 2019)
      AND description ILIKE '%SPLIT%'
    ORDER BY receipt_date, vendor_name, gross_amount DESC
""")

all_splits = cur.fetchall()
print(f"\n📊 Found {len(all_splits)} receipts with SPLIT pattern in 2012/2019\n")

# Group by potential split groups
split_groups = defaultdict(list)
error_log = []

for receipt_id, rec_date, vendor, amount, desc in all_splits:
    rec_year = rec_date.year
    
    # Try to extract split info
    split_info = {
        'receipt_id': receipt_id,
        'date': rec_date,
        'vendor': vendor,
        'amount': float(amount),
        'description': desc or "",
        'split_marker': None,
        'linked_receipt_id': None
    }
    
    # Check for [SPLIT with #XXXXX] pattern
    match_split_with = re.search(r'\[SPLIT\s+with\s+#(\d+)\]', desc or '', re.IGNORECASE)
    if match_split_with:
        split_info['split_marker'] = f"[SPLIT with #{match_split_with.group(1)}]"
        split_info['linked_receipt_id'] = int(match_split_with.group(1))
    
    # Check for SPLIT/amount pattern
    match_split_slash = re.search(r'SPLIT/(\d+\.?\d*)', desc or '', re.IGNORECASE)
    if match_split_slash:
        split_info['split_marker'] = f"SPLIT/{match_split_slash.group(1)}"
    
    # Group by (vendor, date) - receipts from same vendor on same date are likely part of same split
    group_key = (vendor, rec_date)
    split_groups[group_key].append(split_info)

print("\n" + "=" * 100)
print("SPLIT GROUPS BY VENDOR & DATE (2-3 parts per split)")
print("=" * 100)

for (vendor, rec_date), parts in sorted(split_groups.items()):
    if len(parts) >= 2:  # Only show actual splits (2+ parts)
        print(f"\n🔗 {vendor} | {rec_date}")
        total_amount = sum(p['amount'] for p in parts)
        
        for p in sorted(parts, key=lambda x: x['amount'], reverse=True):
            print(f"  Receipt #{p['receipt_id']}: ${p['amount']:>7.2f} | {p['split_marker'] or 'NO MARKER'}")
            if p['description'] and len(p['description']) > 70:
                print(f"    Desc: {p['description'][:70]}")
        
        print(f"  → Total: ${total_amount:.2f}")
        
        # Check for errors
        # Verify at least one has a split marker
        has_marker = any(p['split_marker'] for p in parts)
        if not has_marker:
            error_log.append(f"⚠️ {vendor} {rec_date}: NO SPLIT MARKER found on any receipt!")
        
        # Check if amounts are reasonable (no zero amounts)
        for p in parts:
            if p['amount'] <= 0:
                error_log.append(f"❌ {vendor} {rec_date}: Receipt #{p['receipt_id']} has $0 or negative amount!")

print("\n" + "=" * 100)
print("ERROR LOG")
print("=" * 100)

if error_log:
    print(f"⚠️ {len(error_log)} issue(s) found:\n")
    for error in error_log:
        print(error)
else:
    print("✅ No errors found!")

print("\n" + "=" * 100)
print("DETAILED DESCRIPTION ANALYSIS (for context on how splits were made)")
print("=" * 100)

# Show descriptions with keywords that explain split types
keywords_found = defaultdict(list)

for receipt_id, rec_date, vendor, amount, desc in all_splits:
    desc_lower = (desc or "").lower()
    
    if 'cash' in desc_lower:
        keywords_found['CASH'].append((receipt_id, vendor, amount, desc))
    if 'card' in desc_lower or 'credit' in desc_lower or 'debit' in desc_lower:
        keywords_found['CARD'].append((receipt_id, vendor, amount, desc))
    if 'rebate' in desc_lower or 'fuel rebate' in desc_lower:
        keywords_found['REBATE'].append((receipt_id, vendor, amount, desc))
    if 'fuel' in desc_lower or 'gas' in desc_lower:
        keywords_found['FUEL'].append((receipt_id, vendor, amount, desc))

for keyword, records in sorted(keywords_found.items()):
    print(f"\n📌 {keyword} ({len(records)} receipts):")
    for receipt_id, vendor, amount, desc in records[:3]:  # Show first 3
        print(f"  #{receipt_id} | {vendor} | ${amount:.2f}")
        print(f"    → {desc[:90]}")

cur.close()
conn.close()
