import psycopg2
c=psycopg2.connect('host=localhost dbname=almsdata user=postgres password=ArrowLimousine')
cur=c.cursor()

print("="*80)
print("CHARTERS TABLE:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position")
cols=[r[0] for r in cur.fetchall()]
for col in cols:
    if 'client' in col or 'customer' in col:
        print(f"  {col}")

print("\n" + "="*80)
print("PAYMENTS TABLE:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='payments' ORDER BY ordinal_position")
cols=[r[0] for r in cur.fetchall()]
for col in cols:
    if 'client' in col or 'customer' in col or 'reserve' in col:
        print(f"  {col}")
