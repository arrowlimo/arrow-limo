"""Update Fre to Martinelli's"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("""
    UPDATE beverage_products 
    SET item_name = 'Martinelli''s Sparkling Cider 750ml',
        description = 'Non-alcoholic sparkling apple cider - perfect for celebrations'
    WHERE item_id = 1067
""")

conn.commit()
print("✅ Updated product 1067 to Martinelli's Sparkling Cider")

cur.close()
conn.close()
