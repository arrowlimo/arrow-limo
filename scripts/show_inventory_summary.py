"""Show beverage inventory summary"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("\n📦 BEVERAGE INVENTORY STATUS")
print("=" * 60)

cur.execute('SELECT COUNT(*), SUM(unit_price), AVG(unit_price) FROM beverage_products')
count, total_price, avg_price = cur.fetchone()

print(f"Total Items:       {count}")
print(f"Total Value:       ${total_price:,.2f}" if total_price else "Total Value:       $0.00")
print(f"Average Price:     ${avg_price:.2f}" if avg_price else "Average Price:     $0.00")

print(f"\nBy Category:")

cur.execute("""
    SELECT category, COUNT(*), AVG(unit_price) 
    FROM beverage_products 
    GROUP BY category 
    ORDER BY COUNT(*) DESC
""")

for cat, cnt, avg in cur.fetchall():
    print(f"  {cat:20} {cnt:3d} items  (avg ${avg:.2f})")

print("\n" + "=" * 60)

cur.close()
conn.close()
