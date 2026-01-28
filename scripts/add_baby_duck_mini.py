"""Add Baby Duck 187ml mini bottle"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get max item_id
cur.execute("SELECT MAX(item_id) FROM beverage_products")
max_id = cur.fetchone()[0]

# Add 187ml mini bottle
cur.execute("""
    INSERT INTO beverage_products 
    (item_id, item_name, category, unit_price, our_cost, description, 
     deposit_amount, gst_included, stock_quantity)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
    max_id + 1,
    'Baby Duck Sparkling Wine 187ml (mini)',
    'Champagne',
    5.99,
    4.19,  # 70% of unit_price
    'Classic Canadian sparkling wine - sweet and fruity (mini bottle)',
    0.10,
    True,
    100
))
print(f"✅ Added item {max_id + 1}: Baby Duck 187ml mini ($5.99)")

conn.commit()

print("\n✅ All Baby Duck sizes now available:")
print("   - Baby Duck 187ml mini: $5.99")
print("   - Baby Duck 750ml: $12.99")
print("   - Baby Duck 1.5L: $23.99")

cur.close()
conn.close()
