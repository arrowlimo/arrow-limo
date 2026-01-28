#!/usr/bin/env python3
"""Fix Receipt 58390 - INFINITE INNOVATIONS."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

cur.execute("""
    UPDATE receipts
    SET vendor_name = 'INFINITE INNOVATIONS (USD)',
        description = '$891.37 @ 1.347'
    WHERE receipt_id = 58390
""")

conn.commit()
print(f'✅ Updated {cur.rowcount} rows')

cur.execute("SELECT receipt_id, vendor_name, gross_amount, description FROM receipts WHERE receipt_id=58390")
r = cur.fetchone()
print(f'Receipt 58390: {r[1]} | ${r[2]:.2f} | {r[3]}')

cur.close()
conn.close()
