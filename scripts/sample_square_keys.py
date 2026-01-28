import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor(cursor_factory=RealDictCursor)

print("\nSample Square payment data:\n")
cur.execute("""
    SELECT payment_id, amount, payment_date, reserve_number, payment_key, payment_code_4char, notes
    FROM payments
    WHERE square_payment_id IS NOT NULL
    ORDER BY payment_date DESC
    LIMIT 20
""")

for p in cur.fetchall():
    print(f"ID: {p['payment_id']}")
    print(f"  Amount: ${p['amount']:.2f}, Date: {p['payment_date']}")
    print(f"  Reserve: {p['reserve_number']}, Key: {p['payment_key']}, Code: {p['payment_code_4char']}")
    print(f"  Notes: {p['notes'][:100] if p['notes'] else 'None'}")
    print()

cur.close()
conn.close()
