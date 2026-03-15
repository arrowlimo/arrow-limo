#!/usr/bin/env python3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

cur.execute('''
    SELECT account_code, account_name, account_type
    FROM chart_of_accounts
    WHERE account_code LIKE '6%'
    ORDER BY account_code
''')

results = cur.fetchall()
print(f"{'Code':<8} {'Description':<50} {'Type'}")
print('-' * 90)
for code, name, acct_type in results:
    print(f'{code:<8} {name:<50} {acct_type}')

cur.close()
conn.close()
