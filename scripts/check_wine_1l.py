#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check Wine-White 1L
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Wine - White' AND item_name LIKE '%1L%'")
count, = cur.fetchone()
print(f'Wine - White 1L count: {count}')

# Check Champagne 1L
cur.execute("SELECT COUNT(*) FROM beverage_products WHERE category='Champagne' AND item_name LIKE '%1L%'")
count, = cur.fetchone()
print(f'Champagne 1L count: {count}')

# Total inventory
cur.execute("SELECT COUNT(*) FROM beverage_products")
count, = cur.fetchone()
print(f'Total items: {count}')

cur.close()
conn.close()
