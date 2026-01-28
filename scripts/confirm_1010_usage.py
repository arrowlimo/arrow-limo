#!/usr/bin/env python
import psycopg2, os

conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REMOVED***'))
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code='1010'")
print('receipts with gl_account_code=1010:', cur.fetchone()[0])
cur.execute("SELECT category, COUNT(*) FROM receipts WHERE gl_account_code='1010' GROUP BY category ORDER BY COUNT(*) DESC")
print('categories for 1010:')
for r in cur.fetchall():
    print(r)

cur.execute("SELECT DISTINCT account_number FROM banking_transactions ORDER BY account_number")
accounts = [r[0] for r in cur.fetchall()]
print('\nbanking account_numbers (distinct):', accounts[:20], '... total', len(accounts))
print('contains 1010:', '1010' in accounts)

cur.close(); conn.close()
