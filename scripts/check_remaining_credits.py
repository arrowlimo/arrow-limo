import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT reserve_number, total_amount_due, paid_amount, balance 
    FROM charters 
    WHERE balance < -2000 
    ORDER BY balance
""")

print('\nRemaining 5 urgent credits:')
for r in cur.fetchall():
    print(f'{r[0]}: total_due=${r[1] or 0:.2f}, paid=${r[2] or 0:.2f}, balance=${r[3]:.2f}')

cur.close()
conn.close()
