#!/usr/bin/env python3
"""Add Blind Man Brewing products."""
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
    
    # Blind Man Brewing (Lacombe, AB) - Core varieties
    products = [
        ("Blind Man Brewing Session 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Blonde ale with citrus notes"),
        ("Blind Man Brewing Longshadows IPA 473ml", 5.99, 0.00, "Beer", "Lacombe craft brewery - West Coast IPA"),
        ("Blind Man Brewing Five of Diamonds Pilsner 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Clean pilsner"),
        ("Blind Man Brewing Dwarf Sour Cherry 473ml", 6.49, 0.00, "Beer", "Lacombe craft brewery - Award-winning sour"),
        ("Blind Man Brewing Kettle Sour 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Tart wheat ale"),
        ("Blind Man Brewing Dream Machine Mexican Lager 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Light lager"),
        ("Blind Man Brewing Dark Lager 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - German dark lager"),
        ("Blind Man Brewing Triphammer Robust Porter 473ml", 5.99, 0.00, "Beer", "Lacombe craft brewery - Porter"),
        ("Blind Man Brewing Ichorous Imperial Stout 473ml", 6.99, 0.00, "Beer", "Lacombe craft brewery - Imperial stout"),
        ("Blind Man Brewing New England Pale Ale 473ml", 5.99, 0.00, "Beer", "Lacombe craft brewery - Juicy hazy pale ale"),
        ("Blind Man Brewing May Long Double IPA 473ml", 6.49, 0.00, "Beer", "Lacombe craft brewery - Big double IPA"),
        ("Blind Man Brewing Coffee Stout 473ml", 5.99, 0.00, "Beer", "Lacombe craft brewery - Coffee stout"),
        ("Blind Man Brewing Shelter Belt Blonde Ale 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Blonde ale"),
        ("Blind Man Brewing Kuyt Wheat Beer 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Dutch wheat beer"),
        ("Blind Man Brewing Czech Pale Lager 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Wood-aged lager"),
        ("Blind Man Brewing Radler 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Grapefruit radler"),
        ("Blind Man Brewing Lil Buzz Honey Lager 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Honey lager"),
        ("Blind Man Brewing Raspberry Light Ale 473ml", 5.49, 0.00, "Beer", "Lacombe craft brewery - Raspberry ale"),
        ("Blind Man Brewing Wander Hop Water 355ml", 3.99, 0.00, "Non-Alcoholic", "Lacombe - Hop water, zero alcohol"),
        ("Blind Man Brewing Wander Tropical Hop Water 355ml", 3.99, 0.00, "Non-Alcoholic", "Lacombe - Tropical hop water, zero alcohol"),
        ("Blind Man Brewing Perepllut Barley Wine 473ml", 7.99, 0.00, "Beer", "Lacombe craft brewery - Barley wine"),
        ("Blind Man Brewing Barrel-Aged Brett 24-2 Stock Ale 473ml", 7.99, 0.00, "Beer", "Lacombe craft brewery - Barrel-aged ale"),
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
