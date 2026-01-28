#!/usr/bin/env python3
"""Check for Hey Y'all, Jack Daniels products, and Jaw Drop."""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def check_products():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    searches = [
        ("Hey Y'all", "%hey%all%"),
        ("Jack Daniels and Coke", "%jack daniels%coke%"),
        ("Jack Daniels Punch", "%jack daniels%punch%"),
        ("Jaw Drop", "%jaw drop%"),
    ]
    
    for search_name, pattern in searches:
        print(f"🔍 Checking for {search_name}...")
        cur.execute("""
            SELECT item_id, item_name, unit_price 
            FROM beverage_products 
            WHERE item_name ILIKE %s 
            ORDER BY item_id
        """, (pattern,))
        
        rows = cur.fetchall()
        if rows:
            print(f"✅ Found {len(rows)} product(s):")
            for item_id, item_name, unit_price in rows:
                print(f"   Item {item_id}: {item_name} (${unit_price:.2f})")
        else:
            print(f"❌ No {search_name} products found")
        print()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_products()
