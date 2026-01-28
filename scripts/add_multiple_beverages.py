#!/usr/bin/env python3
"""Add multiple beverage products."""
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
        # Too Hoots Hard Ice Tea
        ("Too Hoots Hard Ice Tea 355ml", 4.49, 0.00, "Hard Seltzers", "Hard ice tea beverage"),
        ("Too Hoots Hard Ice Tea 473ml", 5.49, 0.00, "Hard Seltzers", "Hard ice tea beverage"),
        
        # Absolute Coolers
        ("Absolute Coolers 355ml", 5.99, 0.00, "Ready-To-Drink", "Vodka-based cooler"),
        ("Absolute Coolers 473ml", 7.49, 0.00, "Ready-To-Drink", "Vodka-based cooler"),
        
        # American Vintage
        ("American Vintage Whiskey 750ml", 34.99, 0.00, "Spirits", "Premium American whiskey"),
        
        # Arizona Hard Ice Tea
        ("Arizona Hard Ice Tea 355ml", 4.29, 0.00, "Hard Seltzers", "Hard ice tea beverage"),
        ("Arizona Hard Ice Tea 473ml", 5.29, 0.00, "Hard Seltzers", "Hard ice tea beverage"),
        
        # Bacardi Coolers
        ("Bacardi Coolers 355ml", 5.99, 0.00, "Ready-To-Drink", "Rum-based cooler"),
        ("Bacardi Coolers 473ml", 7.49, 0.00, "Ready-To-Drink", "Rum-based cooler"),
        
        # Mudslide
        ("Mudslide Cocktail 355ml", 6.99, 0.00, "Ready-To-Drink", "Ready-to-drink mudslide"),
        
        # Blackfly Cocktail
        ("Blackfly Cocktail 355ml", 6.99, 0.00, "Ready-To-Drink", "Ready-to-drink cocktail"),
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
        WHERE item_name LIKE '%Too Hoots%' 
           OR item_name LIKE '%Absolute Cooler%' 
           OR item_name LIKE '%American Vintage%' 
           OR item_name LIKE '%Arizona Hard%' 
           OR item_name LIKE '%Bacardi Cooler%' 
           OR item_name LIKE '%Mudslide%' 
           OR item_name LIKE '%Blackfly%'
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
