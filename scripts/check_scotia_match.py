import psycopg2
c = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()
cur.execute("SELECT COUNT(*) as total, COUNT(CASE WHEN receipt_id IS NOT NULL THEN 1 END) as matched FROM banking_transactions WHERE account_number='903990106011' AND debit_amount > 0")
r = cur.fetchone()
print(f'Scotia 903990106011 debits: {r[1]}/{r[0]} matched ({100*r[1]/r[0]:.1f}%)')
c.close()
