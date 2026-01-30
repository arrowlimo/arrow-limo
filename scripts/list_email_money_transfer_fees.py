#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute(
    """
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, source_reference, source_file
    FROM receipts
    WHERE vendor_name ILIKE 'EMAIL MONEY TRANSFER FEE%'
    ORDER BY vendor_name, receipt_date, receipt_id
    """
)
rows = cur.fetchall()
print(f"rows: {len(rows)}")
for r in rows:
    rid, rdate, v, amt, desc, src_ref, src_file = r
    print(f"{rid:>8} | {rdate} | {v:<30} | {amt:>10} | {src_ref or ''} | {desc or ''} | {src_file or ''}")
cur.close(); conn.close()
