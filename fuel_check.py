import psycopg2
conn = psycopg2.connect(host='localhost', port='5432', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT * FROM receipts WHERE category = 'Fuel' LIMIT 1")
if cur.rowcount > 0:
    print("Fuel receipt columns:")
    for desc in cur.description:
        print(f"  - {desc[0]}")
else:
    print("No fuel receipts found")
cur.close()
conn.close()
