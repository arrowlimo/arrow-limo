#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check Global Payments vendor names in database"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("\n" + "="*110)
print("GLOBAL PAYMENTS VENDOR NAMES (Card Transactions)")
print("="*110 + "\n")

# Check banking transactions
cur.execute("""
    SELECT vendor_extracted, COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions
    WHERE description ILIKE '%CARD%'
    AND vendor_extracted IS NOT NULL
    GROUP BY vendor_extracted
    ORDER BY COUNT(*) DESC
""")

results = cur.fetchall()
print(f"{'Vendor Name':<45} {'Count':>6} {'Debits':>15} {'Credits':>15}")
print("-"*110)

for vendor, count, debits, credits in results:
    debits_str = f"${debits:,.2f}" if debits else "$0.00"
    credits_str = f"${credits:,.2f}" if credits else "$0.00"
    print(f"{vendor:<45} {count:>6} {debits_str:>15} {credits_str:>15}")

print(f"\nTotal: {len(results)} distinct vendor names")

# Check for NULL vendor_extracted where description has card info
cur.execute("""
    SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions
    WHERE description ILIKE '%CARD%'
    AND vendor_extracted IS NULL
""")

null_count, null_debits, null_credits = cur.fetchone()
if null_count > 0:
    print(f"\n⚠️  {null_count} card transactions still have NULL vendor_extracted")
    print(f"   Debits: ${null_debits:,.2f}, Credits: ${null_credits:,.2f}")

cur.close()
conn.close()
