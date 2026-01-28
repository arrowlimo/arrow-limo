#!/usr/bin/env python3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
)
cur = conn.cursor()
cur.execute("""
SELECT entity, from_email, subject, email_date, amount, status
FROM email_financial_events
WHERE entity IN ('Heffner','CMB Insurance')
ORDER BY email_date DESC NULLS LAST
LIMIT 50;
""")
rows = cur.fetchall()
for r in rows:
    print(r)
cur.close(); conn.close()
