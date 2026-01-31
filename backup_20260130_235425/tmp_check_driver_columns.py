import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' AND column_name LIKE '%driver%' ORDER BY ordinal_position")
print('Driver-related columns in charters:')
for r in cur.fetchall():
    print(f'  {r[0]}')

# Also check for a sample charter to see what data exists
cur.execute("SELECT reserve_number, driver_name, employee_id FROM charters WHERE reserve_number IS NOT NULL LIMIT 5")
print('\nSample charter data:')
for r in cur.fetchall():
    print(f'  Reserve: {r[0]}, driver_name: {r[1]}, employee_id: {r[2]}')
cur.close()
conn.close()
