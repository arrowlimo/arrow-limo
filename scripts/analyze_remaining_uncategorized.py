#!/usr/bin/env python3
"""Analyze remaining 8,307 uncategorized receipts to find patterns."""

import psycopg2
from collections import defaultdict

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("="*120)
print("REMAINING UNCATEGORIZED RECEIPTS ANALYSIS")
print("="*120)

# Get all uncategorized
cur.execute("""
    SELECT receipt_id, vendor_name, description, gross_amount, category
    FROM receipts
    WHERE (business_personal IS NULL OR business_personal != 'personal')
    AND gl_account_code IS NULL
    ORDER BY gross_amount DESC
""")
uncategorized = cur.fetchall()
print(f"\nTotal uncategorized: {len(uncategorized):,} receipts")

# Analyze by vendor
vendor_counts = defaultdict(lambda: {'count': 0, 'amount': 0})
for r in uncategorized:
    vendor = r[1] or 'Unknown'
    vendor_counts[vendor]['count'] += 1
    vendor_counts[vendor]['amount'] += r[3]

print("\n" + "="*120)
print("TOP 30 VENDORS BY COUNT")
print("="*120)
print(f"{'Vendor':60s} | Count | Total Amount")
print("-"*120)
for vendor, data in sorted(vendor_counts.items(), key=lambda x: x[1]['count'], reverse=True)[:30]:
    print(f"{vendor[:58]:58s} | {data['count']:5d} | ${data['amount']:>12,.2f}")

# Look for common keywords in descriptions
keyword_patterns = defaultdict(lambda: {'count': 0, 'amount': 0})
keywords = [
    'Customer Deposit', 'Refund', 'Reversal', 'Credit', 'Adjustment',
    'Transfer', 'Deposit', 'Unknown Vendor', 'Monthly Summary',
    'Correction', 'PURCHASE', 'DEBIT', 'CREDIT MEMO', 'PAD',
    'PRE-AUTH', 'Insurance', 'License', 'Registration'
]

for r in uncategorized:
    desc = (r[2] or '').upper()
    for keyword in keywords:
        if keyword.upper() in desc:
            keyword_patterns[keyword]['count'] += 1
            keyword_patterns[keyword]['amount'] += r[3]

print("\n" + "="*120)
print("COMMON DESCRIPTION KEYWORDS")
print("="*120)
print(f"{'Keyword':30s} | Count | Total Amount")
print("-"*120)
for keyword, data in sorted(keyword_patterns.items(), key=lambda x: x[1]['count'], reverse=True):
    if data['count'] > 0:
        print(f"{keyword:28s} | {data['count']:5d} | ${data['amount']:>12,.2f}")

# Amount distribution
ranges = [
    (0, 50, '$0-50'),
    (50, 100, '$50-100'),
    (100, 500, '$100-500'),
    (500, 1000, '$500-1000'),
    (1000, 5000, '$1000-5000'),
    (5000, 999999999, '$5000+')
]

print("\n" + "="*120)
print("AMOUNT DISTRIBUTION")
print("="*120)
print(f"{'Range':15s} | Count | Total Amount")
print("-"*120)
for min_amt, max_amt, label in ranges:
    count = sum(1 for r in uncategorized if min_amt <= r[3] < max_amt)
    amount = sum(r[3] for r in uncategorized if min_amt <= r[3] < max_amt)
    print(f"{label:13s} | {count:5d} | ${amount:>12,.2f}")

# Sample some specific uncategorized for pattern recognition
print("\n" + "="*120)
print("SAMPLE UNCATEGORIZED (Random mix)")
print("="*120)
print(f"{'Vendor':40s} | Amount     | Description")
print("-"*120)
import random
sample = random.sample(uncategorized, min(20, len(uncategorized)))
for r in sample:
    vendor = (r[1] or 'Unknown')[:38]
    desc = (r[2] or '')[:60]
    print(f"{vendor:38s} | ${r[3]:>9.2f} | {desc}")

conn.close()
