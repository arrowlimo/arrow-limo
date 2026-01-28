import psycopg2
c = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
r = c.cursor()
r.execute('SELECT * FROM receipts LIMIT 1')
print("Receipts table columns:")
for i, d in enumerate(r.description[:20], 1):
    print(f"{i}. {d[0]}")
c.close()
