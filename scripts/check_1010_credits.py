import psycopg2, os
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT transaction_date, credit_amount, description FROM banking_transactions WHERE account_number = '1010' AND credit_amount > 0 ORDER BY credit_amount DESC")
print("CIBC 1010 Credits (Deposits):")
for row in cur.fetchall():
    print(f"{row[0]} ${row[1]:11,.2f} {row[2] or '(blank)'}")
cur.close()
conn.close()
