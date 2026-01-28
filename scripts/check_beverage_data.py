"""Check beverage_products data for our_cost and image_path"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()
cur.execute("""
    SELECT item_id, item_name, unit_price, our_cost, deposit_amount, image_path
    FROM beverage_products
    WHERE item_id IN (1, 2, 3, 4, 5)
    ORDER BY item_id
""")

print("Sample beverage data:")
print("ID | Name | Unit Price | Our Cost | Deposit | Image Path")
print("-" * 80)
for row in cur.fetchall():
    item_id, name, price, cost, deposit, img = row
    print(f"{item_id} | {name[:30]} | ${price} | ${cost or 0} | ${deposit or 0} | {img or 'None'}")

cur.close()
conn.close()
