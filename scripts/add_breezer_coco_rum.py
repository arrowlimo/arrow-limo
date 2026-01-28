#!/usr/bin/env python3
"""Add Breezer and Coco Rum."""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def add_products():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get max item_id to find next available
    cur.execute("SELECT MAX(item_id) FROM beverage_products")
    max_id = cur.fetchone()[0] or 0
    next_id = max_id + 1
    
    print(f"📊 Max item_id in database: {max_id}, starting from {next_id}")
    
    # Products to add
    products = [
        # Breezer - fruit-flavored malt beverage coolers
        ("Breezer 355ml", 3.99, 0.00, "Ready-To-Drink", "Fruit-flavored malt beverage"),
        ("Breezer 473ml", 4.99, 0.00, "Ready-To-Drink", "Fruit-flavored malt beverage"),
        
        # Coco Rum
        ("Coco Rum 750ml", 22.99, 0.00, "Spirits", "Coconut-flavored rum"),
        ("Coco Rum 1L", 29.99, 0.00, "Spirits", "Coconut-flavored rum"),
    ]
    
    print(f"\n🍾 Adding {len(products)} products...")
    current_id = next_id
    
    for item_name, unit_price, deposit, category, description in products:
        our_cost = round(unit_price * 0.70, 2)
        
        try:
            cur.execute("""
                INSERT INTO beverage_products 
                (item_id, item_name, unit_price, our_cost, deposit_amount, category, description, image_path, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (current_id, item_name, unit_price, our_cost, deposit, category, description, None))
            
            conn.commit()
            print(f"✅ Added item {current_id}: {item_name} (${unit_price:.2f})")
            current_id += 1
        except Exception as e:
            conn.rollback()
            print(f"❌ Error adding {item_name}: {e}")
            current_id += 1
    
    # Verify
    cur.execute("""
        SELECT item_id, item_name, unit_price, category FROM beverage_products 
        WHERE item_name LIKE '%Breezer%' 
           OR item_name LIKE '%Coco Rum%'
        ORDER BY item_id
    """)
    rows = cur.fetchall()
    
    print(f"\n✅ Verification ({len(rows)} products):")
    for item_id, item_name, unit_price, category in rows:
        print(f"   Item {item_id}: {item_name:<45} ${unit_price:>6.2f} ({category})")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    add_products()
