#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
analyze_category_standardization.py

Review and standardize banking_transactions.category and receipts.category
for consistent accounting classification.
"""

import psycopg2
from collections import defaultdict

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(
    host=DB_HOST,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

print("\n" + "="*110)
print("CATEGORY ANALYSIS - BANKING & RECEIPTS")
print("="*110 + "\n")

# Banking categories
print("BANKING TRANSACTION CATEGORIES:")
print("-"*110)
cur.execute("""
    SELECT category, COUNT(*) as tx_count, SUM(debit_amount) as total_debits, SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE verified = TRUE
    GROUP BY category
    ORDER BY COUNT(*) DESC
""")

banking_categories = {}
print(f"{'Category':<40} {'Count':>10} {'Total Debits':>18} {'Total Credits':>18}")
print("-"*110)

for category, count, debits, credits in cur.fetchall():
    cat_display = category if category else '(NULL)'
    debits_display = f"${debits:,.2f}" if debits else "$0.00"
    credits_display = f"${credits:,.2f}" if credits else "$0.00"
    print(f"{cat_display:<40} {count:>10,} {debits_display:>18} {credits_display:>18}")
    banking_categories[category] = count

print(f"\nTotal distinct banking categories: {len(banking_categories)}")

# Receipt categories
print("\n" + "="*110)
print("RECEIPT CATEGORIES:")
print("-"*110)
cur.execute("""
    SELECT category, COUNT(*) as tx_count, SUM(gross_amount) as total_amount
    FROM receipts
    GROUP BY category
    ORDER BY COUNT(*) DESC
""")

receipt_categories = {}
print(f"{'Category':<40} {'Count':>10} {'Total Amount':>18}")
print("-"*110)

for category, count, total in cur.fetchall():
    cat_display = category if category else '(NULL)'
    total_display = f"${total:,.2f}" if total else "$0.00"
    print(f"{cat_display:<40} {count:>10,} {total_display:>18}")
    receipt_categories[category] = count

print(f"\nTotal distinct receipt categories: {len(receipt_categories)}")

# Category overlap analysis
print("\n" + "="*110)
print("CATEGORY COMPARISON")
print("="*110 + "\n")

banking_set = set(banking_categories.keys())
receipt_set = set(receipt_categories.keys())

shared = banking_set & receipt_set
banking_only = banking_set - receipt_set
receipt_only = receipt_set - banking_set

print(f"Shared categories (in both): {len(shared)}")
if shared:
    for cat in sorted(shared, key=lambda x: x if x else ''):
        print(f"  - {cat if cat else '(NULL)'}")

print(f"\nBanking-only categories: {len(banking_only)}")
if banking_only:
    for cat in sorted(banking_only, key=lambda x: x if x else ''):
        print(f"  - {cat if cat else '(NULL)'}")

print(f"\nReceipt-only categories: {len(receipt_only)}")
if receipt_only:
    for cat in sorted(receipt_only, key=lambda x: x if x else ''):
        print(f"  - {cat if cat else '(NULL)'}")

# Vendor-based category suggestions
print("\n" + "="*110)
print("CATEGORY STANDARDIZATION SUGGESTIONS")
print("="*110 + "\n")

print("Based on vendor patterns, suggested category mappings:")
print("-"*110)

category_patterns = {
    'Fuel': ['FAS GAS', 'SHELL', 'PETRO CANADA', 'ESSO', 'HUSKY', 'CO-OP'],
    'Supplies': ['CANADIAN TIRE', 'HOME DEPOT', 'COSTCO', 'WALMART'],
    'Food': ['TIM HORTONS', 'MCDONALDS', 'SUBWAY', 'A&W'],
    'Groceries': ['SUPERSTORE', 'SAFEWAY', 'SOBEYS', '7-ELEVEN'],
    'Vehicle Maintenance': ['OIL CHANGE', 'TIRE', 'CARWASH', 'CAR WASH', 'AUTO'],
    'Insurance': ['INSURANCE', 'INTACT', 'AVIVA'],
    'Bank Fees': ['BANK FEE', 'NSF', 'SERVICE CHARGE', 'MONTHLY FEE'],
    'Merchant Services': ['GLOBAL VISA', 'GLOBAL MASTERCARD', 'GLOBAL AMEX'],
}

for category, patterns in category_patterns.items():
    print(f"\n{category}:")
    for pattern in patterns:
        print(f"  - {pattern}")

# Unknown/NULL categories
print("\n" + "="*110)
print("RECORDS NEEDING CATEGORY ASSIGNMENT")
print("="*110 + "\n")

cur.execute("""
    SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions
    WHERE (category IS NULL OR category = 'Unknown')
    AND verified = TRUE
""")

null_count, null_debits, null_credits = cur.fetchone()
if null_count > 0:
    print(f"Banking transactions with NULL/Unknown category: {null_count:,}")
    print(f"  Total debits: ${null_debits:,.2f}" if null_debits else "  Total debits: $0.00")
    print(f"  Total credits: ${null_credits:,.2f}" if null_credits else "  Total credits: $0.00")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE category IS NULL OR category = 'Unknown'
""")

null_count, null_total = cur.fetchone()
if null_count > 0:
    print(f"\nReceipts with NULL/Unknown category: {null_count:,}")
    print(f"  Total amount: ${null_total:,.2f}" if null_total else "  Total amount: $0.00")

print("\n" + "="*110)
print("ANALYSIS COMPLETE")
print("="*110)
print("\nNext step: Create standardization script based on vendor patterns")

cur.close()
conn.close()
