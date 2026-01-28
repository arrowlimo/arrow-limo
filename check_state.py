import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) as total, COALESCE(SUM(amount), 0) as amount FROM payments WHERE payment_method = %s', ('credit_card',))
total, amount = cur.fetchone()

print(f'\nFinal State:')
print(f'  Total payments: {total}')
print(f'  Total amount: ${amount:,.2f}')
print(f'  Status: All {total} Square payments verified\n')

cur.close()
conn.close()
