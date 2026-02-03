#!/usr/bin/env python3
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute('SELECT account_code, account_name FROM chart_of_accounts ORDER BY account_code')
for code, name in cur.fetchall():
    print(f'{code:<8} {name}')
cur.close()
conn.close()
