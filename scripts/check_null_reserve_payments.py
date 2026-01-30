import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

print('=== NULL RESERVE_NUMBER PAYMENTS ===\n')

pg_cur.execute('''
    SELECT COUNT(*) FROM payments WHERE reserve_number IS NULL
''')
count = pg_cur.fetchone()[0]
print(f'Total NULL reserve_number payments: {count}')

pg_cur.execute('''
    SELECT SUM(amount) FROM payments WHERE reserve_number IS NULL
''')
total = pg_cur.fetchone()[0]
print(f'Total amount: ${total:,.2f}\n')

# Sample 10
print('Sample NULL reserve payments:\n')
pg_cur.execute('''
    SELECT payment_id, amount, payment_date, payment_method, reference_number
    FROM payments
    WHERE reserve_number IS NULL
    ORDER BY payment_date DESC
    LIMIT 10
''')

for payment_id, amount, date, method, ref in pg_cur.fetchall():
    print(f'  ID: {payment_id} | ${amount:>10,.2f} | {date} | Method: {method} | Ref: {ref}')

pg_cur.close()
pg_conn.close()
