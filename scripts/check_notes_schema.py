import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check accounts table for warning/flag columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'accounts' 
    AND (column_name LIKE '%warn%' OR column_name LIKE '%flag%' OR column_name LIKE '%alert%' OR column_name LIKE '%note%')
    ORDER BY ordinal_position
""")
print('=== Accounts Warning/Flag Columns ===')
for row in cur.fetchall():
    print(f'{row[0]:30} {row[1]}')

# Check charters table for notes columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'charters' 
    AND column_name LIKE '%note%'
    ORDER BY ordinal_position
""")
print('\n=== Charters Notes Columns ===')
for row in cur.fetchall():
    print(f'{row[0]:30} {row[1]}')

cur.close()
conn.close()
