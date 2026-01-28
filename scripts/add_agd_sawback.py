#!/usr/bin/env python3
"""Add AGD Classic and Sawback Brewery beers."""
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
    
    # Get max item_id
    cur.execute("SELECT MAX(item_id) FROM beverage_products")
    max_id = cur.fetchone()[0] or 0
    next_id = max_id + 1
    
    print(f"📊 Max item_id: {max_id}, starting from {next_id}\n")
    
    # Products to add
    products = [
        # AGD Classic (Alberta Genuine Draft)
        ("AGD Classic Lager 355ml", 2.49, 0.00, "Beer", "Alberta Genuine Draft lager"),
        ("AGD Classic Lager 473ml", 3.29, 0.00, "Beer", "Alberta Genuine Draft lager"),
        ("AGD Classic Lager 6-pack", 12.99, 0.00, "Beer", "Alberta Genuine Draft 6-pack"),
        
        # Sawback Brewery (Red Deer) - Award-winning varieties
        ("Sawback East Coast Hazy Pale Ale 473ml", 5.99, 0.00, "Beer", "Red Deer craft brewery - Session IPA"),
        ("Sawback Wild West Coast IPA 473ml", 6.49, 0.00, "Beer", "Red Deer craft brewery - Brett beer"),
        ("Sawback Irish Red Ale 473ml", 5.99, 0.00, "Beer", "Red Deer craft brewery - Irish red ale"),
        ("Sawback Passion Fruit Sour 473ml", 6.99, 0.00, "Beer", "Red Deer craft brewery - Fruited sour"),
        ("Sawback Hazy Blonde Ale 473ml", 5.99, 0.00, "Beer", "Red Deer craft brewery - Blonde ale"),
        ("Sawback India Dark Ale 473ml", 6.49, 0.00, "Beer", "Red Deer craft brewery - Specialty IPA"),
        ("Sawback Saison No.1 473ml", 6.49, 0.00, "Beer", "Red Deer craft brewery - Belgian saison"),
        ("Sawback Wild Sour Saison 473ml", 6.99, 0.00, "Beer", "Red Deer craft brewery - Sour saison"),
        ("Sawback West Coast IPA 473ml", 6.49, 0.00, "Beer", "Red Deer craft brewery - West coast IPA"),
    ]
    
    print(f"🍾 Adding {len(products)} products...\n")
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
            print(f"✅ {current_id}: {item_name}")
            current_id += 1
        except Exception as e:
            conn.rollback()
            print(f"❌ Error: {item_name}: {e}")
            current_id += 1
    
    print(f"\n✅ Successfully added {len(products)} products!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    add_products()
