#!/usr/bin/env python3
"""Check for Epitaph Gin."""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def check_product():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("🔍 Checking for Epitaph Gin...")
    cur.execute("""
        SELECT item_id, item_name, unit_price 
        FROM beverage_products 
        WHERE item_name ILIKE '%epitaph%'
        ORDER BY item_id
    """)
    
    rows = cur.fetchall()
    if rows:
        print(f"✅ Found {len(rows)} product(s):")
        for item_id, item_name, unit_price in rows:
            print(f"   Item {item_id}: {item_name} (${unit_price:.2f})")
    else:
        print("❌ No Epitaph Gin products found")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_product()
