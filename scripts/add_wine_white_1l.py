#!/usr/bin/env python3
"""Add missing Wine - White 1L sizes"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get some Wine-White 750ml samples
cur.execute("""
    SELECT item_name, unit_price
    FROM beverage_products 
    WHERE category='Wine - White'
    AND item_name LIKE '%750ml%'
    ORDER BY item_name
    LIMIT 10
""")

items = cur.fetchall()
print(f"Adding Wine - White 1L sizes for {len(items)} brands...\n")

for item_750ml, price_750ml in items:
    price_750ml = float(price_750ml)
    brand = item_750ml.replace(" 750ml", "").strip()
    price_1l = round(price_750ml * 1.33, 2)
    
    # Check if 1L already exists
    cur.execute("""
        SELECT COUNT(*) FROM beverage_products 
        WHERE category='Wine - White' AND item_name=%s
    """, (f"{brand} 1L",))
    
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 1L", "Wine - White", price_1l, f"{brand} white wine - 1L"))
        
        print(f"  ✅ {brand:35} 1L | ${price_1l:.2f}")

conn.commit()
cur.close()
conn.close()

print(f"\nDone!")
