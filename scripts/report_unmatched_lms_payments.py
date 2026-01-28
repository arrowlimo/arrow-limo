import csv
from datetime import datetime
import pyodbc
import psycopg2

LMS_PATH = r'L:\New folder\lms.mdb'

lms_conn = pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')
pg_conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')

lms_cur = lms_conn.cursor()
pg_cur = pg_conn.cursor()

# Load LMS payments
lms_cur.execute("""
    SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy
    FROM Payment
    WHERE Amount IS NOT NULL
""")

rows = lms_cur.fetchall()

# Helper to normalize reserve numbers
def normalize_reserve_number(val):
    if not val:
        return None
    numeric = ''.join(c for c in str(val) if c.isdigit())
    return numeric.zfill(6) if numeric else None

unmatched = []

for r in rows:
    lms_payment_id = r[0]
    account_no = r[1]
    reserve_no = normalize_reserve_number(r[2])
    amount = float(r[3]) if r[3] else 0.0
    payment_key = r[4]
    payment_date = r[5]
    last_updated_by = r[6]

    if not reserve_no:
        continue

    pg_cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_no,))
    res = pg_cur.fetchone()
    if not res:
        unmatched.append({
            'lms_payment_id': lms_payment_id,
            'account_no': account_no,
            'reserve_number': reserve_no,
            'amount': amount,
            'payment_key': payment_key,
            'payment_date': payment_date,
            'last_updated_by': last_updated_by,
        })

# Write CSV
out_path = r'L:\limo\reports\unmatched_lms_payments.csv'
import os
os.makedirs(r'L:\limo\reports', exist_ok=True)

with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['lms_payment_id','account_no','reserve_number','amount','payment_key','payment_date','last_updated_by'])
    w.writeheader()
    for row in unmatched:
        w.writerow({k: (row[k].strftime('%Y-%m-%d %H:%M:%S') if k=='payment_date' and row[k] else row[k]) for k in w.fieldnames})

print(f"Unmatched LMS payments: {len(unmatched)} -> {out_path}")

pg_cur.close()
lms_cur.close()
pg_conn.close()
lms_conn.close()
