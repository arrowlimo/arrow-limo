import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check vendor_account_ledger
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name='vendor_account_ledger' ORDER BY ordinal_position
""")

cols = cur.fetchall()
if cols:
    print("vendor_account_ledger columns:")
    for col in cols:
        print(f"  {col[0]}")
else:
    print("vendor_account_ledger not found")

cur.close()
conn.close()
