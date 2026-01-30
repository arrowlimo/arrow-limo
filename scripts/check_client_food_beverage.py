#!/usr/bin/env python3
"""Check where CLIENT FOOD AND BEVERAGE category went"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("\n" + "="*100)
print("SEARCHING FOR CLIENT FOOD AND BEVERAGE CATEGORY")
print("="*100)

# Search for variations
search_terms = [
    'CLIENT FOOD AND BEVERAGE',
    'Client Food and Beverage',
    'client food and beverage',
    '%client%food%',
    '%food%beverage%',
    '%client%beverage%'
]

for term in search_terms:
    if '%' in term:
        cur.execute("""
            SELECT category, gl_account_code, COUNT(*) as cnt, SUM(COALESCE(gross_amount, 0)) as total
            FROM receipts
            WHERE category ILIKE %s
            GROUP BY category, gl_account_code
            ORDER BY cnt DESC
        """, (term,))
    else:
        cur.execute("""
            SELECT category, gl_account_code, COUNT(*) as cnt, SUM(COALESCE(gross_amount, 0)) as total
            FROM receipts
            WHERE category = %s
            GROUP BY category, gl_account_code
            ORDER BY cnt DESC
        """, (term,))
    
    results = cur.fetchall()
    if results:
        print(f"\n🔍 Search: '{term}'")
        for row in results:
            cat = row[0]
            gl = row[1] or 'NULL'
            cnt = row[2]
            total = row[3]
            print(f"   Category: {cat:<40} GL: {gl:<10} Count: {cnt:>4}  Total: ${total:>12,.2f}")

# Also check for entertainment/meals categories
print("\n" + "="*100)
print("RELATED CATEGORIES (Entertainment/Meals)")
print("="*100)

cur.execute("""
    SELECT category, gl_account_code, COUNT(*) as cnt, SUM(COALESCE(gross_amount, 0)) as total
    FROM receipts
    WHERE category ILIKE '%entertainment%' 
       OR category ILIKE '%meal%'
       OR category ILIKE '%beverage%'
    GROUP BY category, gl_account_code
    ORDER BY cnt DESC
""")

for row in cur.fetchall():
    cat = row[0] or 'NULL'
    gl = row[1] or 'NULL'
    cnt = row[2]
    total = row[3]
    print(f"Category: {cat:<45} GL: {gl:<10} Count: {cnt:>4}  Total: ${total:>12,.2f}")

cur.close()
conn.close()
