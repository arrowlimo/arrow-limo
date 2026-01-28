#!/usr/bin/env python3
"""Add Long Drink, Tequila Smash, Happy Dad, Happy Mom."""
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
        # Long Drink (Finnish-style gin & grapefruit soda)
        ("Long Drink 355ml", 4.49, 0.00, "Ready-To-Drink", "Finnish gin & grapefruit soda"),
        ("Long Drink 473ml", 5.99, 0.00, "Ready-To-Drink", "Finnish gin & grapefruit soda"),
        
        # Tequila Smash
        ("Tequila Smash Cooler 355ml", 6.99, 0.00, "Ready-To-Drink", "Tequila-based cooler"),
        ("Tequila Smash Cooler 473ml", 8.99, 0.00, "Ready-To-Drink", "Tequila-based cooler"),
        
        # Happy Dad (hard seltzer brand)
        ("Happy Dad Hard Seltzer 355ml", 3.99, 0.00, "Hard Seltzers", "Hard seltzer"),
        ("Happy Dad Hard Seltzer 473ml", 4.99, 0.00, "Hard Seltzers", "Hard seltzer"),
        ("Happy Dad Hard Seltzer 12-pack", 34.99, 0.00, "Hard Seltzers", "Hard seltzer 12-pack"),
        
        # Happy Mom (wine-based cocktail)
        ("Happy Mom Wine Cocktail 355ml", 4.99, 0.00, "Ready-To-Drink", "Wine-based cocktail"),
        ("Happy Mom Wine Cocktail 473ml", 6.49, 0.00, "Ready-To-Drink", "Wine-based cocktail"),
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
        WHERE item_name LIKE '%Long Drink%' 
           OR item_name LIKE '%Tequila Smash%'
           OR item_name LIKE '%Happy Dad%'
           OR item_name LIKE '%Happy Mom%'
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
