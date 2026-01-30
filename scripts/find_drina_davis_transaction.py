#!/usr/bin/env python3
import psycopg2
from datetime import date

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REDACTED***',
    'host': 'localhost',
    'port': 5432
}

query = """
SELECT transaction_id, transaction_date, description, credit_amount
FROM banking_transactions
WHERE description ILIKE '%DRINA DAVIS%'
  AND credit_amount BETWEEN 1713.99 AND 1714.01
  AND transaction_date BETWEEN %s AND %s
ORDER BY transaction_date DESC
LIMIT 5;
"""

with psycopg2.connect(**DB_CONFIG) as conn:
    with conn.cursor() as cur:
        cur.execute(query, (date(2025,6,20), date(2025,6,26)))
        rows = cur.fetchall()
        for r in rows:
            print(f"transaction_id={r[0]}, date={r[1]}, amount={r[3]}, desc={r[2]}")
