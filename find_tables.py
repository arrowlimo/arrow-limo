import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find banking tables
cur.execute("""SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' AND table_name LIKE '%bank%'""")
print("Banking tables:", [t[0] for t in cur.fetchall()])

# Find payment-related tables
cur.execute("""SELECT table_name FROM information_schema.tables 
WHERE table_schema='public' AND table_name IN ('payments', 'charters', 'receipts')""")
print("Core tables:", [t[0] for t in cur.fetchall()])

conn.close()
