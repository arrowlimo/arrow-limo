"""Add missing champagne products: Baby Duck and non-alcoholic options"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Get max item_id
cur.execute("SELECT MAX(item_id) FROM beverage_products")
max_id = cur.fetchone()[0] or 1000

new_products = [
    {
        'item_id': max_id + 1,
        'item_name': 'Baby Duck Sparkling Wine 750ml',
        'category': 'Champagne',
        'unit_price': 12.99,
        'our_cost': 9.09,  # 70% of unit_price
        'description': 'Classic Canadian sparkling wine - sweet and fruity',
        'deposit_amount': 0.10
    },
    {
        'item_id': max_id + 2,
        'item_name': 'Non-Alcoholic Sparkling Wine 750ml',
        'category': 'Non-Alcoholic',
        'unit_price': 15.99,
        'our_cost': 11.19,  # 70% of unit_price
        'description': 'Alcohol-free sparkling celebration wine',
        'deposit_amount': 0.10
    },
    {
        'item_id': max_id + 3,
        'item_name': 'Fre Alcohol-Removed Champagne 750ml',
        'category': 'Non-Alcoholic',
        'unit_price': 18.99,
        'our_cost': 13.29,  # 70% of unit_price
        'description': 'Premium alcohol-removed sparkling wine',
        'deposit_amount': 0.10
    }
]

print("Adding missing champagne products...")
for product in new_products:
    cur.execute("""
        INSERT INTO beverage_products 
        (item_id, item_name, category, unit_price, our_cost, description, 
         deposit_amount, gst_included, stock_quantity)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        product['item_id'],
        product['item_name'],
        product['category'],
        product['unit_price'],
        product['our_cost'],
        product['description'],
        product['deposit_amount'],
        True,  # gst_included
        100    # stock_quantity
    ))
    print(f"✅ Added: {product['item_name']} (ID: {product['item_id']}, ${product['unit_price']:.2f})")

conn.commit()

print(f"\n✅ Successfully added {len(new_products)} new products")
print("Note: These products don't have images yet. Add them to L:\\limo\\data\\product_images\\ if needed.")

cur.close()
conn.close()
