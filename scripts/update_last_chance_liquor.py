#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("UPDATE receipts SET vendor_name = 'LAST CHANCE LIQUOR STORE' WHERE vendor_name IN ('LAST CHANCE LIQUOR', 'LAST CHANCE LIQ')")
print(f"updated {cur.rowcount} rows")
conn.commit()
cur.close(); conn.close()
