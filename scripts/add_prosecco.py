"""Add Prosecco products in common sizes"""
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

prosecco_products = [
    {
        'name': 'Prosecco 187ml (mini)',
        'size': '187ml',
        'price': 6.99,
        'description': 'Italian sparkling wine - dry and refreshing (mini bottle)'
    },
    {
        'name': 'Prosecco 750ml',
        'size': '750ml',
        'price': 16.99,
        'description': 'Italian sparkling wine - dry and refreshing'
    },
    {
        'name': 'Prosecco 1.5L',
        'size': '1.5L',
        'price': 29.99,
        'description': 'Italian sparkling wine - dry and refreshing (magnum)'
    }
]

print("Adding Prosecco products...")
for i, product in enumerate(prosecco_products):
    item_id = max_id + i + 1
    our_cost = round(product['price'] * 0.70, 2)
    
    cur.execute("""
        INSERT INTO beverage_products 
        (item_id, item_name, category, unit_price, our_cost, description, 
         deposit_amount, gst_included, stock_quantity)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        item_id,
        product['name'],
        'Champagne',
        product['price'],
        our_cost,
        product['description'],
        0.10,
        True,
        100
    ))
    print(f"✅ Added item {item_id}: {product['name']} (${product['price']:.2f})")

conn.commit()

print(f"\n✅ Successfully added {len(prosecco_products)} Prosecco products")
print("\nAll Prosecco sizes now available:")
for product in prosecco_products:
    print(f"   - {product['name']}: ${product['price']:.2f}")

cur.close()
conn.close()
