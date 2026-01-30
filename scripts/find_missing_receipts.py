import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount 
    FROM receipts 
    WHERE EXTRACT(YEAR FROM receipt_date) < 2012 
    ORDER BY receipt_date
""")

rows = cur.fetchall()
print(f"Missing {len(rows)} receipts from 2007-2011:\n")
for r in rows:
    print(f"{r[0]:6} {r[1]} {r[2]:30} ${r[3]:>10.2f}")

cur.close()
conn.close()
