import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(row[0])
cur.close(); conn.close()
