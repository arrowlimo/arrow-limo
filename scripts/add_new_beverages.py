#!/usr/bin/env python3
"""Add Gin Smash Cooler, Cottage Springs, No Way Ice Tea, and Keystone."""
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
        ("Gin Smash Cooler 355ml", 6.99, 0.00, "Ready-To-Drink", "Gin smash flavored cooler"),
        ("Gin Smash Cooler 473ml", 8.99, 0.00, "Ready-To-Drink", "Gin smash flavored cooler"),
        ("Cottage Springs Water 500ml", 2.99, 0.00, "Water", "Spring water"),
        ("Cottage Springs Water 1L", 3.99, 0.00, "Water", "Spring water"),
        ("No Way Ice Tea 355ml", 3.49, 0.00, "Iced Tea", "Non-alcoholic ice tea"),
        ("No Way Ice Tea 473ml", 4.49, 0.00, "Iced Tea", "Non-alcoholic ice tea"),
        ("Keystone Light Beer 355ml (single)", 2.49, 0.00, "Beer", "Light lager"),
        ("Keystone Light Beer 473ml (single)", 3.29, 0.00, "Beer", "Light lager"),
        ("Keystone Light 24-pack", 29.99, 0.00, "Beer", "Light lager 24-pack"),
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
        SELECT item_id, item_name, unit_price, our_cost, category FROM beverage_products 
        WHERE item_name LIKE '%Gin Smash%' 
           OR item_name LIKE '%Cottage Springs%' 
           OR item_name LIKE '%No Way%' 
           OR item_name LIKE '%Keystone%'
        ORDER BY item_id
    """)
    rows = cur.fetchall()
    
    print(f"\n✅ Verification ({len(rows)} products):")
    for item_id, item_name, unit_price, our_cost, category in rows:
        print(f"   Item {item_id}: {item_name:<40} ${unit_price:>6.2f} ({category})")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    add_products()
