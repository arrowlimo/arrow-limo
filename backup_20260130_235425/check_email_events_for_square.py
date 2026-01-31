#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*)
    FROM email_financial_events
    WHERE subject ILIKE '%square%'
       OR notes ILIKE '%square%'
       OR entity ILIKE '%square%'
""")
count = cur.fetchone()[0]
print(f"Email events mentioning 'square': {count}")

cur.execute("""
    SELECT id, email_date, amount, subject, notes
    FROM email_financial_events
    WHERE subject ILIKE '%square%'
       OR notes ILIKE '%square%'
       OR entity ILIKE '%square%'
    ORDER BY email_date DESC
    LIMIT 20
""")
rows = cur.fetchall()
for row in rows:
    print(row)

cur.close(); conn.close()
