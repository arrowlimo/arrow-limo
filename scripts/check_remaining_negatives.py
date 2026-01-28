"""Check remaining negative 2012 payments"""
import os
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, notes
    FROM payments 
    WHERE payment_date >= '2012-01-01' AND payment_date < '2013-01-01'
      AND amount < 0
    ORDER BY amount
""")

rows = cur.fetchall()
print(f"Remaining {len(rows)} negative 2012 payments:")
print(f"{'ID':<8} {'Date':<12} {'Amount':>10} {'Method':<15} {'Notes':<60}")
print('-' * 115)

for r in rows:
    notes_short = (r[4] or '')[:60]
    print(f"{r[0]:<8} {r[1]} ${float(r[2]):>9,.2f} {(r[3] or 'None'):<15} {notes_short}")

print(f"\nTotal: ${sum(float(r[2]) for r in rows):,.2f}")

cur.close()
conn.close()
