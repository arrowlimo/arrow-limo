import pyodbc

c = pyodbc.connect('Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\\limo\\database_backups\\lms2026.mdb')
cur = c.cursor()

cur.execute('SELECT Account_No, Name, Attention, Bill_To FROM Customer WHERE Account_No = ?', ('07606',))
r = cur.fetchone()

if r:
    print(f'Account: {r[0]}')
    print(f'Name: {r[1] if r[1] else "NULL"}')
    print(f'Attention: {r[2] if r[2] else "NULL"}')
    print(f'Bill_To: {r[3] if r[3] else "NULL"}')
    
    if r[3]:
        print(f'\nLooking up parent account {r[3]}...')
        cur.execute('SELECT Account_No, Name, Attention FROM Customer WHERE Account_No = ?', (r[3],))
        parent = cur.fetchone()
        if parent:
            print(f'Parent Account: {parent[0]}')
            print(f'Parent Name: {parent[1]}')
            print(f'Parent Attention: {parent[2] if parent[2] else "NULL"}')
else:
    print('Account not found')

c.close()
