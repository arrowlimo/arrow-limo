#!/usr/bin/env python3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    port=int(os.getenv('DB_PORT','5432')),
    dbname=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','')
)
conn.autocommit = True
cur = conn.cursor()

print('Constraints on payments:')
cur.execute("""
SELECT c.conname, pg_get_constraintdef(c.oid)
  FROM pg_constraint c
 WHERE c.conrelid = 'payments'::regclass
   AND c.contype = 'c'
""")
for name, defn in cur.fetchall():
    print('-', name, '|', defn)

print('\nDistinct payment_method values present:')
cur.execute("SELECT DISTINCT LOWER(TRIM(payment_method)) FROM payments WHERE payment_method IS NOT NULL ORDER BY 1")
for (m,) in cur.fetchall():
    print('-', m)

cur.close(); conn.close()
