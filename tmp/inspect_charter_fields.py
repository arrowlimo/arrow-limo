import sys, psycopg2
conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='charges' ORDER BY ordinal_position")
print('CHARGES_COLS:', [r[0] for r in cur.fetchall()])

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='vehicles' ORDER BY ordinal_position")
print('VEHICLE_COLS:', [r[0] for r in cur.fetchall()])

cur.execute("SELECT * FROM vehicles WHERE vehicle_id=5")
row = cur.fetchone()
cols = [d[0] for d in cur.description]
print('VEHICLE_ROW:', dict(zip(cols,row)))

# also grab a sample charge from any 2012 charter
cur.execute("SELECT * FROM charges WHERE reserve_number IN (SELECT reserve_number FROM charters WHERE EXTRACT(YEAR FROM charter_date)=2012) LIMIT 3")
rows = cur.fetchall()
cols2 = [d[0] for d in cur.description]
print('CHARGE_SAMPLE_COLS:', cols2)
for r in rows:
    print('CHARGE_ROW:', dict(zip(cols2,r)))
