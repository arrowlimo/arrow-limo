import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Sample unmatched employee banking descriptions:")
cur.execute("""
    SELECT DISTINCT description, COUNT(*) as count
    FROM banking_transactions
    WHERE reconciled_payment_id IS NULL
    AND (
        description ILIKE '%PAUL%RICHARD%'
        OR description ILIKE '%SHERRI%'
        OR description ILIKE '%BARB%PEACOCK%'
        OR description ILIKE '%DAVID%RICHARD%'
        OR description ILIKE '%DAVID%WILL%'
        OR description ILIKE '%MATTHEW%'
        OR description ILIKE '%JERRY%'
        OR description ILIKE '%JEANNIE%'
        OR description ILIKE '%BARBARA%'
        OR description ILIKE '%BRITTANY%'
    )
    GROUP BY description
    ORDER BY count DESC
    LIMIT 40
""")

for i, (desc, count) in enumerate(cur.fetchall(), 1):
    print(f"{i:2d}. ({count:3d}x) {desc[:80]}")

cur.close()
conn.close()
