import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check what's in client_id and what it maps to
cur.execute("""
    SELECT c.reserve_number, c.client_id, c.charter_date,
           cl.client_name, cl.company_name, e.full_name
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    LEFT JOIN employees e ON c.employee_id = e.employee_id
    WHERE c.reserve_number IN ('019769', '019760', '019713')
""")

print('Sample charter data:')
for r in cur.fetchall():
    print(f'  Reserve: {r[0]}, client_id: {r[1]}, charter_date: {r[2]}')
    print(f'    → client_name: {r[3]}, company: {r[4]}, driver: {r[5]}')

# Check what "A Flat of Bud" actually is
cur.execute("""
    SELECT client_id, client_name, company_name, client_type
    FROM clients
    WHERE client_name ILIKE '%flat%' OR client_name ILIKE '%bud%'
       OR company_name ILIKE '%flat%' OR company_name ILIKE '%bud%'
""")

print('\nClients with "flat" or "bud":')
for r in cur.fetchall():
    print(f'  ID: {r[0]}, name: {r[1]}, company: {r[2]}, type: {r[3]}')

# Check date distribution
cur.execute("""
    SELECT MIN(charter_date), MAX(charter_date), COUNT(*)
    FROM charters
""")
r = cur.fetchone()
print(f'\nCharter dates:')
print(f'  Min: {r[0]}, Max: {r[1]}, Total: {r[2]}')

cur.close()
conn.close()
