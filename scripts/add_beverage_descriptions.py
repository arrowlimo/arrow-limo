#!/usr/bin/env python3
"""Add description column to beverage_products table if it doesn't exist"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

try:
    # Check if description column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='beverage_products' AND column_name='description'
    """)
    
    if not cur.fetchone():
        # Add description column
        cur.execute("""
            ALTER TABLE beverage_products 
            ADD COLUMN description VARCHAR(500) DEFAULT NULL
        """)
        conn.commit()
        print("✅ Added description column to beverage_products")
    else:
        print("✅ Description column already exists")
    
    # Update descriptions for existing products with smart defaults
    updates = [
        ("Twisted Tea", "Refreshing malt-based beverage with natural tea flavors"),
        ("Corona", "Light, crisp Mexican lager with citrus notes"),
        ("Heineken", "Classic Dutch pilsner with balanced hop bitterness"),
        ("Guinness", "Rich, creamy Irish stout with coffee and chocolate notes"),
        ("Budweiser", "American lager with subtle sweetness"),
        ("Bud Light", "Light American lager, smooth and refreshing"),
        ("Coors Light", "Light, crisp American lager"),
        ("Vodka", "Neutral spirit, versatile for mixed drinks"),
        ("Rum", "Tropical spirit with caramel and vanilla notes"),
        ("Tequila", "Agave-based spirit, perfect for margaritas"),
        ("Whiskey", "Aged spirit with complex oak and grain flavors"),
        ("Gin", "Botanical spirit with juniper and spice notes"),
        ("Wine - Red", "Full-bodied red wine with tannins and fruit notes"),
        ("Wine - White", "Light, crisp white wine with citrus and floral notes"),
        ("Champagne", "Sparkling wine, celebratory and elegant"),
        ("Cabernet Sauvignon", "Bold red wine with berry and oak flavors"),
        ("Pinot Grigio", "Light white wine with green apple and citrus notes"),
        ("Sauvignon Blanc", "Crisp white wine with herbaceous and tropical notes"),
        ("Merlot", "Smooth red wine with plum and cherry notes"),
        ("Chardonnay", "Rich white wine with butter and oak flavors"),
    ]
    
    for keyword, description in updates:
        cur.execute("""
            UPDATE beverage_products 
            SET description = %s
            WHERE description IS NULL 
            AND item_name ILIKE %s
        """, (description, f'%{keyword}%'))
    
    conn.commit()
    
    # Count updated rows
    cur.execute("""
        SELECT COUNT(*) FROM beverage_products WHERE description IS NOT NULL
    """)
    count = cur.fetchone()[0]
    print(f"✅ Updated descriptions for {count} beverages")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
