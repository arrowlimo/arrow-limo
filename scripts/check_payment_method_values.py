import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check payment_method constraint
cur.execute("""
    SELECT constraint_name, check_clause 
    FROM information_schema.check_constraints 
    WHERE constraint_name LIKE '%payment_method%'
""")
print('Payment method constraints:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Get distinct payment_method values currently in use
cur.execute("""
    SELECT DISTINCT payment_method, COUNT(*) 
    FROM payments 
    WHERE payment_method IS NOT NULL
    GROUP BY payment_method 
    ORDER BY COUNT(*) DESC
""")
print('\nExisting payment_method values:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} payments')

cur.close()
conn.close()
