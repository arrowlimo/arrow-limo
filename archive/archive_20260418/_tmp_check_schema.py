import psycopg2
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()
print("charter_charges columns:")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='charter_charges' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\ncharter_payments columns:")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='charter_payments' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\ncharters columns:")
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

cur.close()
conn.close()
