"""Show beverage_menu contents"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute('SELECT * FROM beverage_menu ORDER BY name')
rows = cur.fetchall()

print("\n📋 beverage_menu table (24 items):\n")
print(f"{'ID':<5} {'Name':<35} {'Category':<15} {'Brand':<15} {'Price':<8}")
print("="*80)

for row in rows:
    beverage_id = row[0]
    name = row[1]
    category = row[2]
    brand = row[3]
    list_price = row[5]
    
    name_str = str(name)[:35] if name else ""
    category_str = str(category)[:15] if category else ""
    brand_str = str(brand)[:15] if brand else ""
    
    print(f"{beverage_id:<5} {name_str:<35} {category_str:<15} {brand_str:<15} ${float(list_price):.2f}")

print("\n" + "="*80)

cur.close()
conn.close()
