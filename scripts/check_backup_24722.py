import psycopg2

c = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = c.cursor()

# Check backup for payment 24722
cur.execute('''
    SELECT payment_id, reserve_number, amount, payment_date, payment_key, created_at 
    FROM payments_backup_waste774_20251123_002119 
    WHERE payment_id = 24722
''')
r = cur.fetchone()

if r:
    print(f'Payment 24722 in backup:')
    print(f'  Reserve: {r[1]}')
    print(f'  Amount: ${float(r[2]):.2f}')
    print(f'  Date: {r[3]}')
    print(f'  Key: {r[4] or "NULL"}')
    print(f'  Created: {r[5]}')
    print()
    print('This payment was deleted as a duplicate but LMS shows it is legitimate.')
    print('Need to restore this payment and the other one (24849 for 019395).')
else:
    print('Payment 24722 not found in backup')
