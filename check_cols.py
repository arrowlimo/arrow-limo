import psycopg2
conn = psycopg2.connect(host='localhost', port='5432', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT * FROM vehicles LIMIT 1")
print("Vehicles columns:")
for desc in cur.description:
    print(f"  - {desc[0]}")
cur.close()
conn.close()
