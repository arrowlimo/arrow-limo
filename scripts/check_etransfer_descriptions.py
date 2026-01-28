import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT description 
    FROM banking_transactions 
    WHERE (description ILIKE %s OR description ILIKE %s)
    AND account_number = '0228362'
    ORDER BY description 
    LIMIT 30
""", ('%e-transfer%', '%interac%'))

print("Sample E-Transfer Banking Descriptions:")
print("="*80)
for row in cur.fetchall():
    print(row[0])

conn.close()
