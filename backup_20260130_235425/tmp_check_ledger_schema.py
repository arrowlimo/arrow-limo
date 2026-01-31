import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'vendor_account_ledger' 
    AND column_name IN ('source_id', 'account_id')
    ORDER BY column_name
""")

print("vendor_account_ledger column types:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

cur.close()
conn.close()
