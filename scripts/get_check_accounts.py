#!/usr/bin/env python3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

cur.execute("SELECT account_number FROM banking_transactions WHERE transaction_id = 60389")
acct = cur.fetchone()[0]
print(f"Check #955.46 Account: {acct}")

cur.execute("SELECT account_number FROM banking_transactions WHERE transaction_id = 60330")
acct2 = cur.fetchone()[0]
print(f"Check WO -120.00 Account: {acct2}")

cur.close()
conn.close()
