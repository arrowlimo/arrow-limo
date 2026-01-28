#!/usr/bin/env python3
"""Find all Apothic wine varieties in beverage_products"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Search for Apothic wines
cur.execute('''
    SELECT item_name, category, unit_price
    FROM beverage_products
    WHERE item_name ILIKE '%apothic%'
    ORDER BY item_name
''')

results = cur.fetchall()
print(f'Found {len(results)} Apothic wine(s):\n')

if results:
    for name, category, price in results:
        print(f'  {name:45} | {category:20} | ${price:7.2f}')
else:
    print('  ✗ No Apothic wines found in database\n')
    print('  AGLC Apothic varieties typically include:')
    print('    - Apothic Red (blend)')
    print('    - Apothic Decadent (blend)')
    print('    - Apothic Inferno (blend)')
    print('    - Apothic Crush (red blend)')
    print('    - Apothic Winemaker Selection (various)\n')

cur.close()
conn.close()
