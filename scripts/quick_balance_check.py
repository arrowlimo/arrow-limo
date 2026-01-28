import psycopg2
c=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REMOVED***')
r=c.cursor()
r.execute("SELECT data_type FROM information_schema.columns WHERE table_name='banking_transactions' AND column_name='balance'")
print('balance column type:', r.fetchone()[0])
r.execute("SELECT transaction_date, debit_amount, credit_amount, balance FROM banking_transactions WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-10' ORDER BY transaction_date, transaction_id LIMIT 10")
print('\nFirst 10 Jan 2012 transactions:')
print(f"{'Date':<12} {'Debit':>10} {'Credit':>10} {'Balance':>12}")
for row in r.fetchall():
    print(f"{str(row[0]):<12} ${row[1] or 0:>8,.2f} ${row[2] or 0:>8,.2f} ${row[3]:>10,.2f}")
c.close()
