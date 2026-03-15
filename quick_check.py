import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost')
cur = conn.cursor()

# Check today's inserts
cur.execute("""
    SELECT COUNT(*), SUM(amount) 
    FROM charter_payments 
    WHERE imported_at::date = CURRENT_DATE 
    AND client_name ILIKE '%Perron Ventures%'
""")

count, total = cur.fetchone()
print(f"Today's payments: {count} records, Total: ${total}")

# Check payment_id column
cur.execute("""
    SELECT payment_id, charter_id, amount
    FROM charter_payments
    WHERE imported_at::date = CURRENT_DATE
    AND client_name ILIKE '%Perron Ventures%'
    LIMIT 5
""")

print("\nSample records:")
for row in cur.fetchall():
    print(f"  payment_id={row[0]}, charter_id={row[1]}, amount={row[2]}")

conn.close()
