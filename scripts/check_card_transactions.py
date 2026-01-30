#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("Searching for MCARD/VCARD/ACARD in descriptions:")

cur.execute("""
    SELECT 
        description,
        vendor_extracted,
        COUNT(*), 
        COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debits,
        COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credits
    FROM banking_transactions
    WHERE (description ILIKE '%mcard%' OR description ILIKE '%vcard%' OR description ILIKE '%acard%')
    AND (description ILIKE '%deposit%' OR description ILIKE '%payment%')
    GROUP BY description, vendor_extracted
    ORDER BY COUNT(*) DESC
    LIMIT 30
""")

results = cur.fetchall()
print(f"\nFound {len(results)} patterns:")
for desc, vendor, count, debits, credits in results:
    desc_str = (desc or '')[:50]
    vendor_str = (vendor or '')[:30]
    print(f"{desc_str:<52} | {vendor_str:<32} | {count:>3} (D:{debits} C:{credits})")

cur.close()
conn.close()
