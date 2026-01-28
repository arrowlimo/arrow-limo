import psycopg2
c = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE '%charge%' ORDER BY table_name")
print('Tables with "charge" in name:')
for r in cur.fetchall():
    print(f'  {r[0]}')

print('\nChecking charter_charges table:')
cur.execute("SELECT COUNT(*) FROM charter_charges")
count = cur.fetchone()[0]
print(f'  Total rows: {count:,}')

cur.execute("SELECT SUM(amount) FROM charter_charges WHERE amount IS NOT NULL")
total = cur.fetchone()[0]
print(f'  Total amount: ${total:,.2f}' if total else '  Total amount: $0.00')

c.close()
