import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT DATE(created_at) as import_date, COUNT(*) 
    FROM banking_transactions 
    WHERE account_number='903990106011' 
    GROUP BY DATE(created_at) 
    ORDER BY import_date
""")

print('Import Date       | Count')
print('-----------------+-------')
for r in cur.fetchall():
    print(f'{r[0]} | {r[1]:,}')

cur.close()
conn.close()
