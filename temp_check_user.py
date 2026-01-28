import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check user and password hash
cur.execute("SELECT username, password_hash, LENGTH(password_hash) as hash_len FROM users WHERE username = 'paulr'")
row = cur.fetchone()

if row:
    print(f'Username: {row[0]}')
    print(f'Hash exists: {row[1] is not None}')
    if row[1]:
        print(f'Hash starts: {row[1][:20]}...')
        print(f'Hash length: {row[2]}')
    else:
        print('NO PASSWORD HASH SET!')
else:
    print('User not found')

cur.close()
conn.close()
