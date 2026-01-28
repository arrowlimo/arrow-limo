#!/usr/bin/env python
import psycopg2, os
conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REMOVED***'))
cur = conn.cursor()
cur.execute("SELECT receipt_id, receipt_date, vendor_name, gross_amount, expense_account, category, gl_account_code, gl_account_name, canonical_vendor FROM receipts WHERE receipt_id IN (139834,139948)")
for r in cur.fetchall():
    print(r)
cur.close(); conn.close()
