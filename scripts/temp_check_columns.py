import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='chart_of_accounts' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(row[0])
