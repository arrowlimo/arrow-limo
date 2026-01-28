import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_receipt_matching_ledger' 
    ORDER BY ordinal_position
""")

cols = cur.fetchall()
print('\nbanking_receipt_matching_ledger columns:')
for col in cols:
    print(f'  {col[0]:30} {col[1]}')

cur.close()
conn.close()
