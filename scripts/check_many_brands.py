#!/usr/bin/env python3
"""Check for multiple beverage brands."""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def check_products():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    searches = [
        ("Mike's Hard Lemonade", "%mike%"),
        ("Mott's Clamato", "%mott%clamato%"),
        ("Nude", "%nude%"),
        ("Muddler", "%muddler%"),
        ("Nutrl", "%nutrl%"),
        ("Ole", "%ole%"),
        ("Palm Bay", "%palm bay%"),
        ("Rev", "%rev%"),
        ("Simply Spiked", "%simply spiked%"),
        ("Smirnoff", "%smirnoff%"),
        ("Snapple", "%snapple%"),
        ("Fireball", "%fireball%"),
        ("Straight and Narrow", "%straight%narrow%"),
        ("SVNS Hard", "%svns%"),
        ("Tempo", "%tempo%"),
        ("Truly", "%truly%"),
        ("Twisted Tea", "%twisted tea%"),
        ("Vizzy", "%vizzy%"),
    ]
    
    missing = []
    found_count = 0
    
    for search_name, pattern in searches:
        cur.execute("""
            SELECT item_id, item_name, unit_price 
            FROM beverage_products 
            WHERE item_name ILIKE %s 
            ORDER BY item_id
        """, (pattern,))
        
        rows = cur.fetchall()
        if rows:
            found_count += 1
            print(f"✅ {search_name}: {len(rows)} product(s)")
        else:
            missing.append(search_name)
            print(f"❌ {search_name}: Not found")
    
    print(f"\n📊 Summary: {found_count} brands found, {len(missing)} missing")
    if missing:
        print(f"\n🔴 Need to add: {', '.join(missing)}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_products()
