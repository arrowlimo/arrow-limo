#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check Vodka
cur.execute("SELECT item_name FROM beverage_products WHERE category='Vodka' ORDER BY item_name LIMIT 20")
print("Vodka items (first 20):")
for item, in cur.fetchall():
    print(f"  {item}")

# Check if there are ANY 750ml vodkas
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Vodka' AND item_name LIKE '%750%'")
count, = cur.fetchone()
print(f"\nVodka 750ml count: {count}")

# Check the overall range
cur.execute("""
    SELECT DISTINCT 
        CASE 
            WHEN item_name LIKE '%50ml%' THEN '50ml'
            WHEN item_name LIKE '%375ml%' THEN '375ml'
            WHEN item_name LIKE '%750ml%' THEN '750ml'
            WHEN item_name LIKE '%1L%' THEN '1L'
            WHEN item_name LIKE '%1.75L%' THEN '1.75L'
            ELSE 'OTHER'
        END as size
    FROM beverage_products
    WHERE category='Vodka'
    ORDER BY size
""")

print("\nVodka sizes present:")
for size, in cur.fetchall():
    print(f"  {size}")

cur.close()
conn.close()
