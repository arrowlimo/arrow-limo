import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check if reserve_number is numeric or text
cur.execute("SELECT reserve_number, client_id, charter_date, employee_id FROM charters LIMIT 3")
print('Sample charters raw:')
for r in cur.fetchall():
    print(f'  Reserve: {r[0]} (type: {type(r[0]).__name__}), client_id: {r[1]}, date: {r[2]}, emp_id: {r[3]}')

# Try with proper casting
cur.execute("""
    SELECT c.reserve_number, c.client_id, c.charter_date, c.employee_id,
           cl.client_name, cl.company_name, e.full_name
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    LEFT JOIN employees e ON c.employee_id = e.employee_id
    WHERE c.reserve_number::text IN ('019609', '019603', '019919')
    LIMIT 3
""")

print('\nChart details:')
for r in cur.fetchall():
    print(f'  Reserve: {r[0]}, client_id: {r[1]}, date: {r[2]}, emp_id: {r[3]}')
    print(f'    → client: {r[4]}, company: {r[5]}, driver: {r[6]}')

cur.close()
conn.close()
