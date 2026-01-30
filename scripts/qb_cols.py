import os,psycopg2
c=psycopg2.connect(host=os.getenv('DB_HOST','localhost'),database='almsdata',user='postgres',password=os.getenv('DB_PASSWORD','***REDACTED***'))
r=c.cursor()
r.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='qb_transactions_staging' ORDER BY ordinal_position")
print("qb_transactions_staging columns:")
for col, dtype in r.fetchall():
    print(f"  {col:<30} {dtype}")
r.close()
c.close()
