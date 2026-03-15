#!/usr/bin/env python3
"""Add missing 750ml bottles for spirits that don't have them"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Find existing spirit bottles to clone 750ml from
cur.execute("""
    SELECT DISTINCT category, item_name 
    FROM beverage_products 
    WHERE category IN ('Vodka', 'Rum', 'Whiskey', 'Gin', 'Tequila', 'Brandy')
    AND item_name LIKE '%1L%'
    ORDER BY category, item_name
""")

to_add = []
for category, item_1l in cur.fetchall():
    # Extract brand name (remove the "1L" part)
    brand = item_1l.replace(" 1L", "").replace(" 1000ml", "").strip()
    
    # Check if 750ml version already exists
    cur.execute("""
        SELECT COUNT(*) FROM beverage_products 
        WHERE category = %s AND (item_name LIKE %s OR item_name LIKE %s)
    """, (category, f"{brand} 750ml", f"{brand} 750"))
    
    count = cur.fetchone()[0]
    if count == 0:
        to_add.append((category, brand))

print(f"Found {len(to_add)} missing 750ml bottles to add:\n")

# Get unit price from 1L bottles to use for 750ml (typically ~85% of 1L price)
for category, brand in to_add:
    cur.execute("""
        SELECT unit_price FROM beverage_products 
        WHERE category = %s AND (item_name LIKE %s OR item_name LIKE %s)
        LIMIT 1
    """, (category, f"{brand} 1L", f"{brand} 1000"))
    
    result = cur.fetchone()
    if result:
        price_1l = float(result[0])
        price_750ml = round(price_1l * 0.85, 2)  # 750ml typically ~85% of 1L
        
        item_name = f"{brand} 750ml"
        
        # Insert the 750ml version
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, 'Premium ' || %s || ' spirit - 750ml bottle')
        """, (item_name, category, price_750ml, brand))
        
        print(f"  ✅ {category:15} | {item_name:40} | ${price_750ml:.2f}")

conn.commit()
cur.close()
conn.close()

print(f"\n✅ Added {len(to_add)} missing 750ml bottles")
