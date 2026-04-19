import csv
import psycopg2
from pathlib import Path

lease_csv = Path(r'l:\limo\data\audit\lease_2012_2014_gst_backfill_candidates_20260407_190606.csv')
ids = []
with lease_csv.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        ids.append(int(row['receipt_id']))

conn = psycopg2.connect(host='localhost',port=5432,dbname='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM receipts WHERE receipt_id = ANY(%s) AND COALESCE(gst_amount,0)=0', (ids,))
print('lease_csv_rows_still_zero_gst', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM receipts WHERE receipt_id = ANY(%s)', (ids,))
print('lease_csv_rows_found', cur.fetchone()[0])
cur.close(); conn.close()
