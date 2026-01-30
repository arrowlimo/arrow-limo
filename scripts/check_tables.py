"""Check what inventory tables exist"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check all tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public'
    ORDER BY table_name
""")

tables = cur.fetchall()
print("All tables in almsdata database:\n")

product_related = []
for (table_name,) in tables:
    if any(keyword in table_name.lower() for keyword in ['product', 'inventory', 'beverage', 'order']):
        product_related.append(table_name)
        print(f"  📦 {table_name}")

if not product_related:
    print("  (No product/inventory/beverage/order tables found)")
    print("\n  Other tables:")
    for (table_name,) in tables[:20]:
        print(f"  - {table_name}")

cur.close()
conn.close()
