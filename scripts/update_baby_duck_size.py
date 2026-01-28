"""Update Baby Duck to 1.5L size"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Update Baby Duck to 1.5L size and adjust price
cur.execute("""
    UPDATE beverage_products 
    SET item_name = 'Baby Duck Sparkling Wine 1.5L',
        unit_price = 19.99,
        our_cost = 13.99,
        description = 'Classic Canadian sparkling wine - sweet and fruity (1.5L magnum)'
    WHERE item_id = 1065
""")

conn.commit()
print("✅ Updated Baby Duck to 1.5L size ($19.99)")

cur.close()
conn.close()
