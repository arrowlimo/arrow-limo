#!/usr/bin/env python3
"""Add Alley Kat Brewery products."""
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
    
    # Get max item_id
    cur.execute("SELECT MAX(item_id) FROM beverage_products")
    max_id = cur.fetchone()[0] or 0
    next_id = max_id + 1
    
    print(f"📊 Max item_id: {max_id}, starting from {next_id}\n")
    
    # Alley Kat Brewery (Edmonton, AB) - Popular varieties
    products = [
        ("Alley Kat Full Moon Pale Ale 473ml", 5.49, 0.00, "Beer", "Edmonton craft brewery - Pale ale"),
        ("Alley Kat Aprikat Apricot Ale 473ml", 5.49, 0.00, "Beer", "Edmonton craft brewery - Fruit ale"),
        ("Alley Kat Charlie Flint's Lager 473ml", 5.49, 0.00, "Beer", "Edmonton craft brewery - Lager"),
        ("Alley Kat Amber Ale 473ml", 5.49, 0.00, "Beer", "Edmonton craft brewery - Amber ale"),
        ("Alley Kat Dragon Series Double IPA 473ml", 6.49, 0.00, "Beer", "Edmonton craft brewery - Double IPA"),
        ("Alley Kat Full Moon Pale Ale 6-pack", 14.99, 0.00, "Beer", "Edmonton craft brewery 6-pack"),
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
