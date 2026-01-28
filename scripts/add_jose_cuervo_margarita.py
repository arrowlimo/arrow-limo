#!/usr/bin/env python3
"""Add Jose Cuervo Margarita ready-to-drink."""
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
    
    # Jose Cuervo Margarita products
    products = [
        ("Jose Cuervo Margarita 355ml", 4.99, 0.00, "Ready-To-Drink", "Ready-to-drink margarita"),
        ("Jose Cuervo Margarita 473ml", 6.49, 0.00, "Ready-To-Drink", "Ready-to-drink margarita"),
        ("Jose Cuervo Margarita 1.75L", 24.99, 0.00, "Ready-To-Drink", "Ready-to-drink margarita"),
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
        SELECT item_id, item_name, unit_price, our_cost FROM beverage_products 
        WHERE item_name LIKE '%Cuervo Margarita%'
        ORDER BY item_id
    """)
    rows = cur.fetchall()
    
    print(f"\n✅ Verification ({len(rows)} products):")
    for item_id, item_name, unit_price, our_cost in rows:
        print(f"   Item {item_id}: {item_name} (${unit_price:.2f}, cost: ${our_cost:.2f})")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    add_products()
