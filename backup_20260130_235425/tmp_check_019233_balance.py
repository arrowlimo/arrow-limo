import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

reserve = '019233'

cur.execute('SELECT SUM(amount) FROM charter_charges WHERE reserve_number = %s', (reserve,))
charges = cur.fetchone()[0]

cur.execute('SELECT SUM(amount) FROM payments WHERE reserve_number = %s', (reserve,))
payments = cur.fetchone()[0]

print(f"Reserve: {reserve}")
print(f"Charges: ${float(charges or 0):.2f}")
print(f"Payments: ${float(payments or 0):.2f}")
print(f"Balance: ${float(charges or 0) - float(payments or 0):.2f}")

cur.close()
conn.close()
