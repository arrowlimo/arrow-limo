"""Check for Prosecco products in database"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Search for Prosecco products
cur.execute("""
    SELECT item_id, item_name, category, unit_price, our_cost, image_path
    FROM beverage_products
    WHERE LOWER(item_name) LIKE '%prosecco%'
    ORDER BY item_name
""")

rows = cur.fetchall()
if rows:
    print(f"Found {len(rows)} Prosecco products:")
    print("-" * 90)
    print(f"{'ID':<5} {'Name':<45} {'Category':<15} {'Price':<8} {'Image'}")
    print("-" * 90)
    for row in rows:
        item_id, name, category, price, cost, img = row
        img_status = "✓" if img else "✗"
        print(f"{item_id:<5} {name[:45]:<45} {category or 'N/A':<15} ${price:<7.2f} {img_status}")
else:
    print("❌ No Prosecco products found in database")
    print("\nWould you like to add Prosecco to the beverage catalog?")

cur.close()
conn.close()
