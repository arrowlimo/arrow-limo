import os, psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'journal' ORDER BY ordinal_position")
print('Journal columns:')
for r in cur.fetchall():
    print(f'  - {r[0]}')
conn.close()
