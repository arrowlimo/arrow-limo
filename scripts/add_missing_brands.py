#!/usr/bin/env python3
"""Add missing beverage brands."""
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
        # Mott's Clamato
        ("Mott's Clamato Caesar 355ml", 3.49, 0.00, "Mixers", "Caesar mix"),
        ("Mott's Clamato Caesar 1.89L", 7.99, 0.00, "Mixers", "Caesar mix"),
        
        # Nude (vodka soda)
        ("Nude Vodka Soda 355ml", 3.49, 0.00, "Hard Seltzers", "Vodka soda"),
        ("Nude Vodka Soda 473ml", 4.49, 0.00, "Hard Seltzers", "Vodka soda"),
        
        # Muddler (craft cocktails)
        ("Muddler Craft Cocktail 355ml", 5.99, 0.00, "Ready-To-Drink", "Craft cocktail"),
        
        # Nutrl (vodka seltzer)
        ("Nutrl Vodka Seltzer 355ml", 3.29, 0.00, "Hard Seltzers", "Vodka seltzer"),
        ("Nutrl Vodka Seltzer 473ml", 4.29, 0.00, "Hard Seltzers", "Vodka seltzer"),
        
        # Palm Bay
        ("Palm Bay 355ml", 3.49, 0.00, "Ready-To-Drink", "Fruit-flavored cooler"),
        ("Palm Bay 473ml", 4.49, 0.00, "Ready-To-Drink", "Fruit-flavored cooler"),
        
        # Rev (energy cooler)
        ("Rev Energy Cooler 473ml", 4.99, 0.00, "Ready-To-Drink", "Energy cooler"),
        
        # Simply Spiked (lemonade)
        ("Simply Spiked Lemonade 355ml", 3.99, 0.00, "Ready-To-Drink", "Spiked lemonade"),
        ("Simply Spiked Lemonade 473ml", 4.99, 0.00, "Ready-To-Drink", "Spiked lemonade"),
        
        # Snapple (hard tea)
        ("Snapple Hard Tea 355ml", 3.99, 0.00, "Hard Seltzers", "Hard iced tea"),
        ("Snapple Hard Tea 473ml", 4.99, 0.00, "Hard Seltzers", "Hard iced tea"),
        
        # Straight and Narrow (non-alcoholic spirits)
        ("Straight and Narrow Non-Alc Spirit 750ml", 29.99, 0.00, "Non-Alcoholic", "Non-alcoholic spirit"),
        
        # SVNS Hard (hard coffee)
        ("SVNS Hard Coffee 355ml", 5.49, 0.00, "Ready-To-Drink", "Hard coffee"),
        
        # Tempo (gin & tonic)
        ("Tempo Gin & Tonic 355ml", 4.99, 0.00, "Ready-To-Drink", "Gin & tonic RTD"),
        ("Tempo Gin & Tonic 473ml", 6.49, 0.00, "Ready-To-Drink", "Gin & tonic RTD"),
        
        # Vizzy (hard seltzer)
        ("Vizzy Hard Seltzer 355ml", 3.29, 0.00, "Hard Seltzers", "Hard seltzer"),
        ("Vizzy Hard Seltzer 473ml", 4.29, 0.00, "Hard Seltzers", "Hard seltzer"),
        ("Vizzy Hard Seltzer 12-pack", 29.99, 0.00, "Hard Seltzers", "Hard seltzer 12-pack"),
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
