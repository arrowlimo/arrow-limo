"""Add both Baby Duck sizes: 1.5L and 750ml"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Update existing Baby Duck to 1.5L
cur.execute("""
    UPDATE beverage_products 
    SET item_name = 'Baby Duck Sparkling Wine 1.5L',
        unit_price = 23.99,
        our_cost = 16.79,
        description = 'Classic Canadian sparkling wine - sweet and fruity (1.5L magnum)'
    WHERE item_id = 1065
""")
print("✅ Updated item 1065: Baby Duck 1.5L ($23.99)")

# Add 750ml size as new product
cur.execute("SELECT MAX(item_id) FROM beverage_products")
max_id = cur.fetchone()[0]

cur.execute("""
    INSERT INTO beverage_products 
    (item_id, item_name, category, unit_price, our_cost, description, 
     deposit_amount, gst_included, stock_quantity)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
    max_id + 1,
    'Baby Duck Sparkling Wine 750ml',
    'Champagne',
    12.99,
    9.09,  # 70% of unit_price
    'Classic Canadian sparkling wine - sweet and fruity',
    0.10,
    True,
    100
))
print(f"✅ Added item {max_id + 1}: Baby Duck 750ml ($12.99)")

conn.commit()

print("\n✅ Both Baby Duck sizes now available:")
print("   - Baby Duck 1.5L: $23.99")
print("   - Baby Duck 750ml: $12.99")

cur.close()
conn.close()
