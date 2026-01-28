#!/usr/bin/env python3
"""Check for Blind Man products."""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

cur.execute("""
    SELECT item_id, item_name FROM beverage_products 
    WHERE item_name ILIKE '%blind man%' 
    ORDER BY item_id
""")

results = cur.fetchall()
if results:
    print(f"✅ Found {len(results)} Blind Man products:")
    for item_id, item_name in results:
        print(f"   {item_id}: {item_name}")
else:
    print("❌ No Blind Man products found")

cur.close()
conn.close()
