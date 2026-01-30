import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("QB_ACCOUNTS columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='qb_accounts' ORDER BY ordinal_position")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\nCHART_OF_ACCOUNTS columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='chart_of_accounts' ORDER BY ordinal_position")
for r in cur.fetchall():
    print(f"  {r[0]}")

cur.close()
conn.close()
