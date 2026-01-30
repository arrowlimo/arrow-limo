import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

# Check charter_payments for duplicates
cur.execute("""
    SELECT charter_id, payment_date, amount, COUNT(*) as count
    FROM charter_payments
    WHERE source IN ('batch_deposit_allocation', 'charter_refund')
    GROUP BY charter_id, payment_date, amount
    HAVING COUNT(*) > 1
    LIMIT 10
""")

print("Potential duplicates in charter_payments (by charter_id, payment_date, amount):")
duplicates = cur.fetchall()
if duplicates:
    for row in duplicates:
        print(f"  Charter {row['charter_id']}, {row['payment_date']}: ${row['amount']} appears {row['count']} times")
else:
    print("  None found")

# Check what's in charter_payments with consolidation source
cur.execute("""
    SELECT COUNT(*) as count, source
    FROM charter_payments
    GROUP BY source
    ORDER BY count DESC
""")

print("\ncharter_payments by source:")
for row in cur.fetchall():
    print(f"  {row['source'] or 'NULL'}: {row['count']:,}")

cur.close()
conn.close()
