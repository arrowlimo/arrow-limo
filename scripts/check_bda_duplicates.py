import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

# Check for duplicate (charter_id, payment_date, amount) in batch_deposit_allocations
cur.execute("""
    SELECT 
        bda.reserve_number as charter_id,
        c.charter_date as payment_date,
        bda.allocation_amount as amount,
        COUNT(*) as count
    FROM batch_deposit_allocations bda
    JOIN charters c ON c.reserve_number = bda.reserve_number
    GROUP BY bda.reserve_number, c.charter_date, bda.allocation_amount
    HAVING COUNT(*) > 1
""")

duplicates = cur.fetchall()
print(f"Duplicate (charter_id, payment_date, amount) combinations in batch_deposit_allocations JOIN charters: {len(duplicates)}")

if duplicates:
    print("\nSample duplicates:")
    for row in duplicates[:5]:
        print(f"  Charter {row['charter_id']}, {row['payment_date']}: ${row['amount']:.2f} - {row['count']} times")

# Check what's using c.charter_date as payment_date
cur.execute("""
    SELECT 
        bda.allocation_amount,
        COUNT(*) as count,
        SUM(bda.allocation_amount) as total
    FROM batch_deposit_allocations bda
    JOIN charters c ON c.reserve_number = bda.reserve_number
    GROUP BY bda.allocation_amount
    ORDER BY count DESC
    LIMIT 10
""")

print("\nTop 10 allocation amounts by frequency:")
for row in cur.fetchall():
    print(f"  ${row['allocation_amount']:.2f}: {row['count']:,} times = ${row['total']:,.2f}")

cur.close()
conn.close()
