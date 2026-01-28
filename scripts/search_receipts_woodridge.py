#!/usr/bin/env python3
import psycopg2
from datetime import date

START = date(2018,9,1)
END = date(2019,6,30)

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("""
  SELECT id, receipt_date, vendor_name, gross_amount, description
  FROM receipts
    WHERE receipt_date BETWEEN %s AND %s
      AND UPPER(COALESCE(vendor_name,'')) LIKE '%%WOODRIDGE%%'
    ORDER BY receipt_date
""", (START, END))
rows = cur.fetchall()
print(f"Receipts: {len(rows)}")
for r in rows:
  rid, rdate, vendor, gross, desc = r
  print(f"  {rdate}  receipt {rid}  ${gross or 0:.2f}  {vendor or ''}\n    {str(desc or '')[:180]}")
cur.close(); conn.close()
