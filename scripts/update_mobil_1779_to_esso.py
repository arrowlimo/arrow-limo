#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("UPDATE receipts SET vendor_name = 'ESSO' WHERE vendor_name = 'MOBIL@ - 1779'")
print(f"updated {cur.rowcount} rows")
conn.commit()
cur.close(); conn.close()
