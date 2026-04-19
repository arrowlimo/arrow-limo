import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='banking_transactions' ORDER BY ordinal_position")
for c, t in cur.fetchall():
    print(f"{c}|{t}")
cur.close()
conn.close()
