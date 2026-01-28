import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

reserve = '019517'

cur.execute("""
    SELECT charter_id, total_amount_due, paid_amount, balance
    FROM charters WHERE reserve_number = %s
""", (reserve,))
c = cur.fetchone()

print(f"\nCharter {reserve}:")
print(f"  Total: ${c[1]:,.2f}")
print(f"  Paid: ${c[2]:,.2f}")
print(f"  Balance: ${c[3]:,.2f}")

cur.execute("""
    SELECT payment_date, amount, LEFT(notes, 60) as notes_short
    FROM payments
    WHERE reserve_number = %s
    ORDER BY payment_date
""", (reserve,))

print(f"\nPayments:")
for p in cur.fetchall():
    print(f"  {p[0]} - ${p[1]:,.2f} - {p[2] or ''}")

cur.close()
conn.close()
