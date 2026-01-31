#!/usr/bin/env python3
"""Add Coco Vodka, Bud Light Cheladas/Hard Soda, Coors Seltzers, Corona Coolers, Vodka Water."""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

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
        # Coco Vodka
        ("Coco Vodka 750ml", 24.99, 0.00, "Spirits", "Coconut-flavored vodka"),
        ("Coco Vodka 1L", 31.99, 0.00, "Spirits", "Coconut-flavored vodka"),
        
        # Bud Light Cheladas
        ("Bud Light Chelada 355ml", 2.99, 0.00, "Beer", "Bud Light with lime and spices"),
        ("Bud Light Chelada 473ml", 3.99, 0.00, "Beer", "Bud Light with lime and spices"),
        
        # Bud Light Hard Soda
        ("Bud Light Hard Soda 355ml", 3.49, 0.00, "Hard Seltzers", "Hard soda beverage"),
        ("Bud Light Hard Soda 473ml", 4.49, 0.00, "Hard Seltzers", "Hard soda beverage"),
        
        # Coors Seltzers
        ("Coors Seltzer 355ml", 2.79, 0.00, "Hard Seltzers", "Crisp hard seltzer"),
        ("Coors Seltzer 473ml", 3.59, 0.00, "Hard Seltzers", "Crisp hard seltzer"),
        ("Coors Seltzer 12-pack", 29.99, 0.00, "Hard Seltzers", "Crisp hard seltzer 12-pack"),
        
        # Corona Coolers
        ("Corona Cooler 355ml", 4.99, 0.00, "Ready-To-Drink", "Corona-based cooler"),
        ("Corona Cooler 473ml", 6.49, 0.00, "Ready-To-Drink", "Corona-based cooler"),
        
        # Vodka Water
        ("Vodka Water 355ml", 5.99, 0.00, "Ready-To-Drink", "Vodka-infused water"),
        ("Vodka Water 473ml", 7.49, 0.00, "Ready-To-Drink", "Vodka-infused water"),
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
        WHERE item_name LIKE '%Coco Vodka%' 
           OR item_name LIKE '%Bud Light Chelada%'
           OR item_name LIKE '%Bud Light Hard Soda%'
           OR item_name LIKE '%Coors Seltzer%'
           OR item_name LIKE '%Corona Cooler%'
           OR item_name LIKE '%Vodka Water%'
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
