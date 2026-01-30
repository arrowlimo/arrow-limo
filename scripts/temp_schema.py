import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='chart_of_accounts' ORDER BY ordinal_position")
for r in cur.fetchall():
    print(f"{r[0]:30} {r[1]}")
