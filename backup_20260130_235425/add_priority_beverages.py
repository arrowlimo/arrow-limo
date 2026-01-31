#!/usr/bin/env python3
"""Add priority beverages to beverage_products table"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Priority items to add with realistic AGLC pricing
priority_items = [
    # Apothic wines
    ("Apothic Red 750ml", "Wine - Red", 18.99, "Red blend with berry and spice notes"),
    ("Apothic Red 1L", "Wine - Red", 24.99, "Red blend with berry and spice notes"),
    ("Apothic Decadent 750ml", "Wine - Red", 21.99, "Premium red blend with caramel and vanilla"),
    ("Apothic Decadent 1L", "Wine - Red", 28.99, "Premium red blend with caramel and vanilla"),
    ("Apothic Inferno 750ml", "Wine - Red", 19.99, "Spiced red blend with dark fruit"),
    ("Apothic Inferno 1L", "Wine - Red", 25.99, "Spiced red blend with dark fruit"),
    
    # Barefoot Cabernet (already exists but add 1L size)
    ("Barefoot Cabernet 1L", "Wine - Red", 24.99, "California Cabernet, smooth and fruit-forward"),
    
    # Premium liqueurs
    ("Jägermeister 50ml", "Liqueurs", 3.50, "German herbal liqueur, 35% ABV"),
    ("Jägermeister 375ml", "Liqueurs", 16.99, "German herbal liqueur, 35% ABV"),
    ("Jägermeister 750ml", "Liqueurs", 32.99, "German herbal liqueur, 35% ABV"),
    
    # Hennessy Cognac
    ("Hennessy VS 50ml", "Brandy", 4.99, "French cognac, smooth oak and vanilla"),
    ("Hennessy VS 375ml", "Brandy", 28.99, "French cognac, smooth oak and vanilla"),
    ("Hennessy VS 750ml", "Brandy", 54.99, "French cognac, smooth oak and vanilla"),
    ("Hennessy VSOP 750ml", "Brandy", 72.99, "Premium French cognac, aged complexity"),
    
    # Additional craft beers
    ("Parallel 49 Brewing 355ml", "Craft Beer", 2.80, "Vancouver craft brewery, bold flavors"),
    ("Parallel 49 Brewing 473ml", "Craft Beer", 3.99, "Vancouver craft brewery, bold flavors"),
    ("Shed & Breakfast IPA 355ml", "Craft Beer", 2.75, "Alberta IPA, citrus and pine hops"),
    ("Shed & Breakfast IPA 473ml", "Craft Beer", 3.95, "Alberta IPA, citrus and pine hops"),
    
    # Premium non-alcoholic
    ("San Pellegrino Sparkling Water 500ml", "Water", 3.50, "Italian sparkling mineral water"),
    ("San Pellegrino Aranciata Orange", "Soft Drinks", 2.99, "Italian blood orange soda"),
]

try:
    added = 0
    skipped = 0
    
    for name, category, price, description in priority_items:
        # Check if already exists
        cur.execute(
            "SELECT COUNT(*) FROM beverage_products WHERE item_name = %s",
            (name,)
        )
        
        if cur.fetchone()[0] == 0:
            # Insert new item
            cur.execute(
                """INSERT INTO beverage_products 
                   (item_name, category, unit_price, description)
                   VALUES (%s, %s, %s, %s)""",
                (name, category, price, description)
            )
            added += 1
            print(f"  ✓ Added: {name:45} | ${price:7.2f}")
        else:
            skipped += 1
            print(f"  ⊘ Skipped (exists): {name}")
    
    conn.commit()
    
    # Get updated count
    cur.execute("SELECT COUNT(*) FROM beverage_products")
    total = cur.fetchone()[0]
    
    print(f"\n✅ Complete!")
    print(f"   Added: {added} new items")
    print(f"   Skipped: {skipped} (already exist)")
    print(f"   Total beverages now: {total:,}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()
