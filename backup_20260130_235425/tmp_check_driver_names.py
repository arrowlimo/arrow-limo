import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check what's in driver_name for charters with "Roma" or similar
cur.execute("""
    SELECT reserve_number, driver_name, employee_id, 
           cl.company_name, cl.client_name
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.driver_name ILIKE '%roma%' OR c.driver_name ILIKE '%rest%'
    LIMIT 20
""")

print('Charters with restaurant-like driver names:')
for r in cur.fetchall():
    print(f'  Reserve: {r[0]}, driver_name: {r[1]}, employee_id: {r[2]}, company: {r[3]}, client: {r[4]}')

# Also check the distribution of NULL vs populated driver_name
cur.execute("""
    SELECT 
        COUNT(*) FILTER (WHERE driver_name IS NULL) as null_count,
        COUNT(*) FILTER (WHERE driver_name IS NOT NULL) as not_null_count,
        COUNT(*) as total
    FROM charters
""")
r = cur.fetchone()
print(f'\nDriver name distribution:')
print(f'  NULL: {r[0]}')
print(f'  NOT NULL: {r[1]}')
print(f'  Total: {r[2]}')

# Sample of actual driver names
cur.execute("""
    SELECT DISTINCT driver_name
    FROM charters
    WHERE driver_name IS NOT NULL
    ORDER BY driver_name
    LIMIT 15
""")
print(f'\nSample driver names:')
for r in cur.fetchall():
    print(f'  {r[0]}')

cur.close()
conn.close()
