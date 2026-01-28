"""Fix beverage products: add our_cost and verify image paths"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check current state
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(our_cost) as has_cost,
        COUNT(image_path) as has_image,
        COUNT(CASE WHEN our_cost IS NULL OR our_cost = 0 THEN 1 END) as missing_cost
    FROM beverage_products
""")
stats = cur.fetchone()
print(f"Total products: {stats[0]}")
print(f"Has our_cost: {stats[1]}")
print(f"Has image_path: {stats[2]}")
print(f"Missing/zero our_cost: {stats[3]}")

# Sample data check
cur.execute("""
    SELECT item_id, item_name, unit_price, our_cost, image_path
    FROM beverage_products
    ORDER BY item_id
    LIMIT 5
""")
print("\nSample products:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1][:30]} | Price: ${row[2]} | Cost: ${row[3] or 0} | Image: {row[4] or 'None'}")

# Update our_cost if missing (assume 70% of unit_price as wholesale cost)
print("\n🔧 Setting our_cost to 70% of unit_price where missing...")
cur.execute("""
    UPDATE beverage_products
    SET our_cost = ROUND(unit_price * 0.70, 2)
    WHERE our_cost IS NULL OR our_cost = 0
""")
updated = cur.rowcount
print(f"✅ Updated {updated} products with estimated wholesale cost")

conn.commit()

# Verify
cur.execute("""
    SELECT item_id, item_name, unit_price, our_cost, 
           ROUND(unit_price - our_cost, 2) as profit_per_unit
    FROM beverage_products
    ORDER BY item_id
    LIMIT 10
""")
print("\nVerification (first 10 products):")
print("ID | Name | Unit Price | Our Cost | Profit/Unit")
print("-" * 70)
for row in cur.fetchall():
    print(f"{row[0]} | {row[1][:25]} | ${row[2]:.2f} | ${row[3]:.2f} | ${row[4]:.2f}")

cur.close()
conn.close()
print("\n✅ Done! Restart app to see profit calculations.")
