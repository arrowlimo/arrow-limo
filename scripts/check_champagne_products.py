"""Check champagne products in database"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Search for champagne-related products
cur.execute("""
    SELECT item_id, item_name, category, unit_price, our_cost, image_path
    FROM beverage_products
    WHERE LOWER(item_name) LIKE '%champagne%' 
       OR LOWER(item_name) LIKE '%baby duck%'
       OR LOWER(category) LIKE '%champagne%'
    ORDER BY item_name
""")

rows = cur.fetchall()
print(f"Found {len(rows)} champagne-related products:")
print("-" * 100)
print(f"{'ID':<5} {'Name':<40} {'Category':<15} {'Price':<8} {'Cost':<8} {'Image'}")
print("-" * 100)
for row in rows:
    item_id, name, category, price, cost, img = row
    img_status = "✓" if img else "✗"
    print(f"{item_id:<5} {name[:40]:<40} {category or 'N/A':<15} ${price:<7.2f} ${cost or 0:<7.2f} {img_status}")

# Check for Baby Duck specifically
cur.execute("""
    SELECT COUNT(*) FROM beverage_products
    WHERE LOWER(item_name) LIKE '%baby%duck%'
""")
baby_duck_count = cur.fetchone()[0]
print(f"\nBaby Duck products found: {baby_duck_count}")

# Check for non-alcoholic champagne
cur.execute("""
    SELECT COUNT(*) FROM beverage_products
    WHERE (LOWER(item_name) LIKE '%non%alcoholic%' OR LOWER(item_name) LIKE '%alcohol%free%')
      AND (LOWER(item_name) LIKE '%champagne%' OR LOWER(item_name) LIKE '%sparkling%')
""")
non_alc_count = cur.fetchone()[0]
print(f"Non-alcoholic champagne/sparkling products found: {non_alc_count}")

cur.close()
conn.close()
