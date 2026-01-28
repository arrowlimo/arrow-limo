#!/usr/bin/env python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Check current state
cur.execute("""SELECT 
    COUNT(*) total,
    COUNT(banking_transaction_id) with_link,
    COUNT(CASE WHEN display_color = 'GREEN' THEN 1 END) green_count,
    COUNT(CASE WHEN banking_transaction_id IS NULL THEN 1 END) no_link
FROM receipts""")

total, linked, green, no_link = cur.fetchone()
print(f'Total receipts: {total:,}')
print(f'With banking_transaction_id: {linked:,}')
print(f'GREEN (display_color): {green:,}')
print(f'Without banking link: {no_link:,}')
print()
print(f'Link coverage: {linked/total*100:.1f}%')

cur.close()
conn.close()
