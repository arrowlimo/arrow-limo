"""
Search for actual description text in 2019 receipts
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("SEARCHING 2019 DESCRIPTIONS...")

# Search for various patterns
patterns = [
    ('SUPPLIES', r'supplies'),
    ('WATER', r'water'),
    ('ICE', r'\bice\b'),
    ('CLIENT', r'client'),
]

for name, pattern in patterns:
    cur.execute("""
        SELECT description, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019
          AND description ~* %s
        GROUP BY description
        ORDER BY COUNT(*) DESC
        LIMIT 10
    """, (pattern,))
    
    results = cur.fetchall()
    print(f"\n{name} ({len(results)} unique descriptions):")
    for desc, count, total in results:
        print(f"  '{desc}' - {count} times, ${total:,.2f}")

cur.close()
conn.close()
