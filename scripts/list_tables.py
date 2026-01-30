import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public' AND table_type='BASE TABLE' 
    ORDER BY table_name
""")
tables = [r[0] for r in cur.fetchall()]
print('\n'.join(tables))
print(f'\n--- {len(tables)} total tables ---')
conn.close()
