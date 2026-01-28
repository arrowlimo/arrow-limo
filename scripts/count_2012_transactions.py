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

cur.execute("""
    SELECT COUNT(*), SUM(COALESCE(debit_amount, 0) + COALESCE(credit_amount, 0)) as total_volume
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

count, volume = cur.fetchone()
print(f"Account 0228362 (CIBC) - 2012:")
print(f"  Total transactions: {count}")
print(f"  Total volume: ${float(volume):,.2f}")

cur.close()
conn.close()
