import os
import psycopg2
try:
    conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password=os.getenv('ALMS_DB_PASSWORD', ''))
    cur = conn.cursor()
    cur.execute('SELECT * FROM charter_routes LIMIT 0')
    print('charter_routes:', [desc[0] for desc in cur.description])
    cur.execute('SELECT * FROM charter_charges LIMIT 0')
    print('charter_charges:', [desc[0] for desc in cur.description])
    cur.execute('SELECT * FROM charter_payments LIMIT 0')
    print('charter_payments:', [desc[0] for desc in cur.description])
    cur.close()
    conn.close()
except Exception as e:
    print(f'Error: {e}')
