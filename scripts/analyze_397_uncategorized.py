#!/usr/bin/env python3
"""Analyze the 397 remaining uncategorized receipts."""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*120)
print("REMAINING UNCATEGORIZED RECEIPTS ANALYSIS")
print("="*120)

# Get uncategorized receipts
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, category
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    ORDER BY gross_amount DESC
""")

uncategorized = cur.fetchall()
print(f"\nTotal uncategorized: {len(uncategorized)} receipts")

if len(uncategorized) == 0:
    print("\n✅ ALL RECEIPTS CATEGORIZED!")
    conn.close()
    exit(0)

# Amount distribution
ranges = [
    (0, 10, '$0-10'),
    (10, 50, '$10-50'),
    (50, 100, '$50-100'),
    (100, 500, '$100-500'),
    (500, 1000, '$500-1000'),
    (1000, 999999, '$1000+')
]

print("\n" + "="*120)
print("AMOUNT DISTRIBUTION")
print("="*120)
print(f"{'Range':15s} | Count | Total Amount | Avg Amount")
print("-"*120)
for min_amt, max_amt, label in ranges:
    subset = [r for r in uncategorized if min_amt <= r[3] < max_amt]
    count = len(subset)
    total = sum(r[3] for r in subset)
    avg = total / count if count > 0 else 0
    print(f"{label:13s} | {count:5d} | ${total:>11,.2f} | ${avg:>9.2f}")

total_amount = sum(r[3] for r in uncategorized)
print("-"*120)
print(f"{'TOTAL':13s} | {len(uncategorized):5d} | ${total_amount:>11,.2f} | ${total_amount/len(uncategorized):>9.2f}")

# Vendor analysis
vendor_counts = defaultdict(lambda: {'count': 0, 'amount': 0})
for r in uncategorized:
    vendor = r[2] or 'Unknown'
    vendor_counts[vendor]['count'] += 1
    vendor_counts[vendor]['amount'] += r[3]

print("\n" + "="*120)
print("TOP 30 VENDORS")
print("="*120)
print(f"{'Vendor':60s} | Count | Total Amount")
print("-"*120)
for vendor, data in sorted(vendor_counts.items(), key=lambda x: x[1]['count'], reverse=True)[:30]:
    print(f"{vendor[:58]:58s} | {data['count']:5d} | ${data['amount']:>11,.2f}")

# Category field analysis (what category value do they have if any)
category_counts = defaultdict(int)
for r in uncategorized:
    category_counts[r[5] or 'NULL'] += 1

print("\n" + "="*120)
print("CATEGORY FIELD VALUES (for uncategorized receipts)")
print("="*120)
print(f"{'Category':30s} | Count")
print("-"*120)
for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"{cat:28s} | {count:5d}")

# Sample high-value uncategorized
print("\n" + "="*120)
print("HIGH-VALUE UNCATEGORIZED (Top 30)")
print("="*120)
print(f"{'ID':8s} | {'Date':12s} | {'Amount':>10s} | {'Vendor':30s} | Description")
print("-"*120)
for r in uncategorized[:30]:
    vendor = (r[2] or 'Unknown')[:28]
    desc = (r[4] or '')[:40]
    print(f"{r[0]:8d} | {r[1]!s:12s} | ${r[3]:>9.2f} | {vendor:28s} | {desc}")

# Look for patterns in descriptions
print("\n" + "="*120)
print("COMMON DESCRIPTION KEYWORDS")
print("="*120)

keywords = defaultdict(int)
for r in uncategorized:
    desc = (r[4] or '').upper()
    words = desc.split()
    for word in words:
        if len(word) > 3:  # Skip short words
            keywords[word] += 1

print(f"{'Keyword':30s} | Occurrences")
print("-"*120)
for word, count in sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:30]:
    if count > 2:  # Only show words appearing 3+ times
        print(f"{word[:28]:28s} | {count:5d}")

# Check if any have category but no GL code
cur.execute("""
    SELECT category, COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    AND category IS NOT NULL
    GROUP BY category
    ORDER BY COUNT(*) DESC
""")

cat_no_gl = cur.fetchall()
if cat_no_gl:
    print("\n" + "="*120)
    print("RECEIPTS WITH CATEGORY BUT NO GL CODE")
    print("="*120)
    print(f"{'Category':30s} | Count | Total Amount")
    print("-"*120)
    for cat, count, amount in cat_no_gl:
        print(f"{cat:28s} | {count:5d} | ${amount:>11,.2f}")

conn.close()
