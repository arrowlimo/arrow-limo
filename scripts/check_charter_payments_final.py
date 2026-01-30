import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)

cur = conn.cursor(cursor_factory=RealDictCursor)

# Check charter_payments totals
cur.execute("SELECT COUNT(*) as count FROM charter_payments")
total = cur.fetchone()['count']
print(f"Total charter_payments: {total:,}")

# Check sources
cur.execute("""
    SELECT source, COUNT(*) as count
    FROM charter_payments
    GROUP BY source
    ORDER BY count DESC
""")

print("\nBy source:")
for row in cur.fetchall():
    print(f"  {row['source'] or 'NULL'}: {row['count']:,}")

# Check max ID
cur.execute("SELECT MAX(id) as max_id FROM charter_payments")
max_id = cur.fetchone()['max_id']
print(f"\nMax charter_payments.id: {max_id}")

# Look for BDA payments
cur.execute("SELECT COUNT(*) FROM charter_payments WHERE payment_key LIKE 'BDA_%'")
bda_count = cur.fetchone()[0]
print(f"BDA_* payments: {bda_count:,}")

cur.close()
conn.close()
