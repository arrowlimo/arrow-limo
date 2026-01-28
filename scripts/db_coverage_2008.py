#!/usr/bin/env python3
"""
Quick coverage check for 2008 in journal and receipts, plus overall min/max dates.
Run with: python scripts/db_coverage_2008.py
"""
import os
import psycopg2

CFG = {
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432')),
}

START = '2008-01-01'
END = '2009-01-01'

conn = psycopg2.connect(**CFG)
cur = conn.cursor()

print('--- Date coverage (journal) ---')
try:
    cur.execute('SELECT MIN("Date"), MAX("Date") FROM journal')
    print('min,max =', cur.fetchone())
    cur.execute('SELECT COUNT(*) FROM journal WHERE "Date" >= %s AND "Date" < %s', (START, END))
    print('rows in 2008 =', cur.fetchone()[0])
except Exception as e:
    print('journal error:', e)

print('\n--- Date coverage (receipts) ---')
try:
    cur.execute('SELECT MIN(receipt_date), MAX(receipt_date) FROM receipts')
    print('min,max =', cur.fetchone())
    cur.execute('SELECT COUNT(*) FROM receipts WHERE receipt_date >= %s AND receipt_date < %s', (START, END))
    print('rows in 2008 =', cur.fetchone()[0])
except Exception as e:
    print('receipts error:', e)

cur.close()
conn.close()
print('\nDone.')