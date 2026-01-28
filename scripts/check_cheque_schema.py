#!/usr/bin/env python3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

cur.execute("SELECT * FROM cheque_register LIMIT 1")
print("cheque_register columns:", [d[0] for d in cur.description])

cur.close()
conn.close()
