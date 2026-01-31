#!/usr/bin/env python3
"""Check if any Square payments have customer names populated."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check ALL Square payments for customer names
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN square_customer_name IS NOT NULL AND square_customer_name != '' THEN 1 END) as with_name,
        COUNT(CASE WHEN square_customer_name IS NULL OR square_customer_name = '' THEN 1 END) as without_name
    FROM payments
    WHERE square_payment_id IS NOT NULL
""")
total, with_name, without_name = cur.fetchone()

print(f'Total Square payments: {total}')
print(f'With customer name: {with_name} ({with_name/total*100:.1f}%)')
print(f'Without customer name: {without_name} ({without_name/total*100:.1f}%)')

# Show a few examples WITH names
cur.execute("""
    SELECT payment_id, square_payment_id, square_customer_name, amount, payment_date
    FROM payments
    WHERE square_payment_id IS NOT NULL
    AND square_customer_name IS NOT NULL
    AND square_customer_name != ''
    LIMIT 20
""")
examples = cur.fetchall()

if examples:
    print(f'\nExamples with customer names ({len(examples)}):')
    for pid, sq_id, name, amt, pdate in examples:
        print(f'  Payment {pid} | {pdate} | ${amt:,.2f} | Customer: {name}')
else:
    print('\nNo payments found with customer names.')

cur.close()
conn.close()
