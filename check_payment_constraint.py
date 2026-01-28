import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Query from pg_constraint
cur.execute("""
    SELECT c.conname, pg_get_constraintdef(c.oid)
    FROM pg_constraint c
    JOIN pg_class r ON c.conrelid = r.oid
    WHERE r.relname = 'payments' AND c.contype = 'c'
""")

for name, def_text in cur.fetchall():
    print(f'{name}:')
    print(f'  {def_text}')
    print()

cur.close()
conn.close()
