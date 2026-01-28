import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

# Check payment status constraint
cur.execute("""
    SELECT con.conname, pg_get_constraintdef(con.oid)
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    WHERE rel.relname = 'payments'
    AND con.conname LIKE '%status%'
""")

print("Payment status constraints:")
for row in cur.fetchall():
    print(f"\n{row[0]}:")
    print(f"  {row[1]}")

cur.close()
conn.close()
