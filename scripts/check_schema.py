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

cur.execute("SELECT * FROM banking_transactions WHERE transaction_id = 60389 LIMIT 1")
print("Columns:", [d[0] for d in cur.description])
result = cur.fetchone()
if result:
    print("\nValues for transaction 60389:")
    for i, col in enumerate([d[0] for d in cur.description]):
        print(f"  {col}: {result[i]}")

cur.close()
conn.close()
