import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT tablename 
    FROM pg_tables 
    WHERE schemaname = 'public' 
    AND tablename LIKE '%scotia%backup%' 
    ORDER BY tablename DESC
""")

tables = cur.fetchall()
print('Scotia backup tables:')
if tables:
    for t in tables:
        print(f'  {t[0]}')
else:
    print('  None found')

conn.close()
