#!/usr/bin/env python3
"""Add Sips champagne to beverage catalog."""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def add_sips():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Sips champagne products - Premium sparkling wine
    products = [
        ("Sips Champagne 187ml (mini)", 8.99, 0.00),    # Single serve bottle
        ("Sips Champagne 750ml", 19.99, 0.00),          # Standard bottle
        ("Sips Champagne 1.5L", 34.99, 0.00),           # Magnum bottle
    ]
    
    print("Adding Sips champagne products...")
    for item_name, unit_price, deposit in products:
        # Calculate our_cost at 70% (wholesale estimate)
        our_cost = round(unit_price * 0.70, 2)
        
        try:
            cur.execute("""
                INSERT INTO beverage_products 
                (item_name, unit_price, our_cost, deposit_amount, category, description, image_path, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING item_id
            """, (item_name, unit_price, our_cost, deposit, "Champagne", "Premium sparkling champagne", None))
            item_id = cur.fetchone()[0]
            conn.commit()
            print(f"✅ Added item {item_id}: {item_name} (${unit_price:.2f})")
        except Exception as e:
            conn.rollback()
            print(f"❌ Error adding {item_name}: {e}")
    
    cur.close()
    conn.close()
    print("\n✅ Successfully added Sips champagne products")

if __name__ == "__main__":
    add_sips()
