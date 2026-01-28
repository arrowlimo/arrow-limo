#!/usr/bin/env python3
"""Check for Fireball and Sips/Sipes champagne in database."""
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
    
    # Check for Fireball
    print("🔍 Checking for Fireball...")
    cur.execute("""
        SELECT item_id, item_name, unit_price, our_cost, deposit_amount 
        FROM beverage_products 
        WHERE item_name ILIKE '%fireball%' 
        ORDER BY item_id
    """)
    fireball_rows = cur.fetchall()
    if fireball_rows:
        print(f"✅ Found {len(fireball_rows)} Fireball product(s):")
        for row in fireball_rows:
            print(f"   Item {row[0]}: {row[1]} (${row[2]:.2f})")
    else:
        print("❌ No Fireball products found")
    
    # Check for Sips/Sipes champagne
    print("\n🔍 Checking for Sips/Sipes champagne...")
    cur.execute("""
        SELECT item_id, item_name, unit_price, our_cost, deposit_amount 
        FROM beverage_products 
        WHERE item_name ILIKE '%sip%' 
        ORDER BY item_id
    """)
    sips_rows = cur.fetchall()
    if sips_rows:
        print(f"✅ Found {len(sips_rows)} Sips/Sipes product(s):")
        for row in sips_rows:
            print(f"   Item {row[0]}: {row[1]} (${row[2]:.2f})")
    else:
        print("❌ No Sips/Sipes products found")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_products()
