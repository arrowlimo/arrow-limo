#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Count remaining duplicates
cur.execute("""
    SELECT COUNT(DISTINCT banking_transaction_id)
    FROM (
        SELECT banking_transaction_id, COUNT(*) as cnt
        FROM receipts
        WHERE banking_transaction_id IS NOT NULL
        GROUP BY banking_transaction_id
        HAVING COUNT(*) > 1
    ) sub
""")

remaining = cur.fetchone()[0]
print(f"Remaining banking transactions with duplicates: {remaining}")

if remaining > 0:
    cur.execute("""
        SELECT banking_transaction_id, COUNT(*) as cnt
        FROM receipts
        WHERE banking_transaction_id IS NOT NULL
        GROUP BY banking_transaction_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """)
    
    print("\nTop 5 worst cases:")
    for row in cur.fetchall():
        print(f"  TX #{row[0]}: {row[1]} receipts")

cur.close()
conn.close()
