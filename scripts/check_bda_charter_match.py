import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

# Check batch_deposit_allocations
cur.execute("SELECT COUNT(*) as count FROM batch_deposit_allocations")
print(f"batch_deposit_allocations: {cur.fetchone()['count']:,}")

# Check if all have matching charters
cur.execute("""
    SELECT COUNT(*) as count
    FROM batch_deposit_allocations bda
    LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
    WHERE c.reserve_number IS NULL
""")
unmatched = cur.fetchone()['count']
print(f"batch_deposit_allocations without matching charter: {unmatched:,}")

# Check matched counts
cur.execute("""
    SELECT COUNT(*) as count
    FROM batch_deposit_allocations bda
    JOIN charters c ON c.reserve_number = bda.reserve_number
""")
matched = cur.fetchone()['count']
print(f"batch_deposit_allocations with matching charter: {matched:,}")

# Sample unmatched
cur.execute("""
    SELECT DISTINCT bda.reserve_number
    FROM batch_deposit_allocations bda
    LEFT JOIN charters c ON c.reserve_number = bda.reserve_number
    WHERE c.reserve_number IS NULL
    LIMIT 10
""")
print(f"\nSample unmatched reserve_numbers:")
for row in cur.fetchall():
    print(f"  {row['reserve_number']}")

cur.close()
conn.close()
