#!/usr/bin/env python3
"""Add missing wine 1L sizes and fill beer gaps"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get some sample wines to price 1L sizes
cur.execute("""
    SELECT DISTINCT item_name 
    FROM beverage_products 
    WHERE category IN ('Wine - White', 'Champagne')
    AND item_name LIKE '%750ml%'
    ORDER BY item_name
    LIMIT 5
""")

samples = [r[0] for r in cur.fetchall()]
print(f"Adding missing wine 1L sizes...\n")

added = 0
for sample_item in samples:
    # Extract brand (remove size)
    brand = sample_item.replace(" 750ml", "").strip()
    category = "Wine - White" if "White" in sample_item else "Champagne"
    
    # Check if 1L already exists
    cur.execute("""
        SELECT COUNT(*) FROM beverage_products 
        WHERE category = %s AND item_name LIKE %s
    """, (category, f"{brand} 1L"))
    
    if cur.fetchone()[0] == 0:
        # Get the 750ml price to estimate 1L price
        cur.execute("""
            SELECT unit_price FROM beverage_products 
            WHERE item_name = %s
        """, (sample_item,))
        
        result = cur.fetchone()
        if result:
            price_750 = float(result[0])
            price_1l = round(price_750 * 1.33, 2)  # 1L is typically ~33% more
            
            cur.execute("""
                INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
                VALUES (%s, %s, %s, 0, %s)
            """, (f"{brand} 1L", category, price_1l, f"{brand} wine - 1L bottle"))
            
            print(f"  ✅ {category:20} | {brand:30} 1L | ${price_1l:.2f}")
            added += 1

conn.commit()

# Add popular beer sizes
print(f"\nAdding missing popular beer sizes...\n")

# Add 473ml to regular Beer
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Beer' AND item_name LIKE '%473ml%'")
if cur.fetchone()[0] == 0:
    # Get a sample beer to clone
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Beer' AND item_name LIKE '%355ml%' LIMIT 1")
    result = cur.fetchone()
    if result:
        sample_beer, price_355 = result
        price_355 = float(price_355)
        brand = sample_beer.replace(" 355ml", "").strip()
        price_473 = round(price_355 * 1.33, 2)
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 473ml", "Beer", price_473, f"{brand} beer - 473ml can"))
        
        print(f"  ✅ Beer                 | {brand:30} 473ml | ${price_473:.2f}")
        added += 1

# Add 12-pack to Craft Beer
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Craft Beer' AND item_name LIKE '%12-pack%'")
if cur.fetchone()[0] == 0:
    # Get a sample craft beer
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Craft Beer' AND item_name LIKE '%6-pack%' LIMIT 1")
    result = cur.fetchone()
    if result:
        sample_beer, price_6pack = result
        price_6pack = float(price_6pack)
        brand = sample_beer.replace(" 6-pack", "").strip()
        price_12pack = round(price_6pack * 1.9, 2)
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 12-pack", "Craft Beer", price_12pack, f"{brand} craft beer - 12-pack"))
        
        print(f"  ✅ Craft Beer           | {brand:30} 12-pack | ${price_12pack:.2f}")
        added += 1

# Add 6-pack to Ciders
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Ciders' AND item_name LIKE '%6-pack%'")
if cur.fetchone()[0] == 0:
    # Get a sample cider
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Ciders' AND item_name LIKE '%355ml%' LIMIT 1")
    result = cur.fetchone()
    if result:
        sample_cider, price_355 = result
        price_355 = float(price_355)
        brand = sample_cider.replace(" 355ml", "").strip()
        price_6pack = round(price_355 * 6.5, 2)  # 6-pack is cheaper per unit
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 6-pack", "Ciders", price_6pack, f"{brand} cider - 6-pack"))
        
        print(f"  ✅ Ciders               | {brand:30} 6-pack | ${price_6pack:.2f}")
        added += 1

conn.commit()
cur.close()
conn.close()

print(f"\n✅ Total items added: {added}")
