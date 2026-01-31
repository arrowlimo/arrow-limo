#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check remaining NULL vendor card transactions"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("\n" + "="*110)
print("REMAINING CARD TRANSACTIONS WITH NULL VENDOR")
print("="*110 + "\n")

cur.execute("""
    SELECT description, COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions
    WHERE description ILIKE '%card%'
    AND vendor_extracted IS NULL
    GROUP BY description
    ORDER BY COUNT(*) DESC
    LIMIT 30
""")

results = cur.fetchall()
print(f"{'Description':<75} {'Count':>6} {'Debits':>13} {'Credits':>13}")
print("-"*110)

for desc, count, debits, credits in results:
    debits_str = f"${debits:,.2f}" if debits else "$0.00"
    credits_str = f"${credits:,.2f}" if credits else "$0.00"
    print(f"{desc[:73]:<75} {count:>6} {debits_str:>13} {credits_str:>13}")

cur.close()
conn.close()
