#!/usr/bin/env python3
"""Add remaining beer pack sizes for full coverage"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("Adding remaining beer/cooler pack sizes...\n")

# Add 6-pack to Beer
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Beer' AND item_name LIKE '%6-pack%'")
if cur.fetchone()[0] == 0:
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Beer' AND item_name LIKE '%355ml%' ORDER BY item_name LIMIT 1")
    result = cur.fetchone()
    if result:
        sample, price_355 = result
        price_355 = float(price_355)
        brand = sample.replace(" 355ml", "").strip()
        price_6pack = round(price_355 * 6 * 0.9, 2)  # 6-pack with 10% discount
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 6-pack", "Beer", price_6pack, f"{brand} beer - 6-pack"))
        
        print(f"  ✅ Beer                 | {brand:35} 6-pack | ${price_6pack:.2f}")

# Add 12-pack to Beer
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Beer' AND item_name LIKE '%12-pack%'")
if cur.fetchone()[0] == 0:
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Beer' AND item_name LIKE '%355ml%' ORDER BY item_name LIMIT 1")
    result = cur.fetchone()
    if result:
        sample, price_355 = result
        price_355 = float(price_355)
        brand = sample.replace(" 355ml", "").strip()
        price_12pack = round(price_355 * 12 * 0.85, 2)  # 12-pack with 15% discount
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 12-pack", "Beer", price_12pack, f"{brand} beer - 12-pack"))
        
        print(f"  ✅ Beer                 | {brand:35} 12-pack | ${price_12pack:.2f}")

# Add 6-pack to Hard Seltzers
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Hard Seltzers' AND item_name LIKE '%6-pack%'")
if cur.fetchone()[0] == 0:
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Hard Seltzers' AND item_name LIKE '%355ml%' ORDER BY item_name LIMIT 1")
    result = cur.fetchone()
    if result:
        sample, price_355 = result
        price_355 = float(price_355)
        brand = sample.replace(" 355ml", "").strip()
        price_6pack = round(price_355 * 6 * 0.9, 2)
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 6-pack", "Hard Seltzers", price_6pack, f"{brand} seltzer - 6-pack"))
        
        print(f"  ✅ Hard Seltzers        | {brand:35} 6-pack | ${price_6pack:.2f}")

# Add 12-pack to Hard Seltzers
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Hard Seltzers' AND item_name LIKE '%12-pack%'")
if cur.fetchone()[0] == 0:
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Hard Seltzers' AND item_name LIKE '%355ml%' ORDER BY item_name LIMIT 1")
    result = cur.fetchone()
    if result:
        sample, price_355 = result
        price_355 = float(price_355)
        brand = sample.replace(" 355ml", "").strip()
        price_12pack = round(price_355 * 12 * 0.85, 2)
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 12-pack", "Hard Seltzers", price_12pack, f"{brand} seltzer - 12-pack"))
        
        print(f"  ✅ Hard Seltzers        | {brand:35} 12-pack | ${price_12pack:.2f}")

# Add 12-pack to Ciders
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Ciders' AND item_name LIKE '%12-pack%'")
if cur.fetchone()[0] == 0:
    cur.execute("SELECT item_name, unit_price FROM beverage_products WHERE category='Ciders' AND item_name LIKE '%355ml%' ORDER BY item_name LIMIT 1")
    result = cur.fetchone()
    if result:
        sample, price_355 = result
        price_355 = float(price_355)
        brand = sample.replace(" 355ml", "").strip()
        price_12pack = round(price_355 * 12 * 0.85, 2)
        
        cur.execute("""
            INSERT INTO beverage_products (item_name, category, unit_price, stock_quantity, description)
            VALUES (%s, %s, %s, 0, %s)
        """, (f"{brand} 12-pack", "Ciders", price_12pack, f"{brand} cider - 12-pack"))
        
        print(f"  ✅ Ciders               | {brand:35} 12-pack | ${price_12pack:.2f}")

conn.commit()

# Check total inventory
cur.execute("SELECT COUNT(*) FROM beverage_products")
total, = cur.fetchone()
print(f"\n✅ Total beverages: {total}")

cur.close()
conn.close()
