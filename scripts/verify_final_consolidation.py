import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor(cursor_factory=RealDictCursor)

print("="*100)
print("FINAL CONSOLIDATION STATUS")
print("="*100)

# Check charges
cur.execute("SELECT COUNT(*) as count FROM charter_charges WHERE tag = 'consolidation_import'")
charges = cur.fetchone()['count']
print(f"\ncharter_charges (consolidation_import): {charges:,}")

# Check payments by source
cur.execute("""
    SELECT source, COUNT(*) as count, SUM(amount) as total
    FROM charter_payments
    GROUP BY source
    ORDER BY count DESC
""")

print("\ncharter_payments by source:")
for row in cur.fetchall():
    print(f"  {row['source'] or 'NULL':30} {row['count']:>8,} rows = ${row['total']:>15,.2f}")

# Check payment mismatches again
cur.execute("""
    SELECT 
        COUNT(*) as mismatched_count,
        SUM(CASE WHEN c.paid_amount > COALESCE(SUM(cp.amount), 0) THEN 1 ELSE 0 END) as underpaid,
        SUM(CASE WHEN c.paid_amount < COALESCE(SUM(cp.amount), 0) THEN 1 ELSE 0 END) as overpaid,
        SUM(ABS(c.paid_amount - COALESCE(SUM(cp.amount), 0))) as total_mismatch
    FROM charters c
    LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
    WHERE c.cancelled = FALSE
      AND c.charter_date >= '2012-01-01'
      AND c.paid_amount > 0
    GROUP BY c.charter_date, c.reserve_number
    HAVING ABS(c.paid_amount - COALESCE(SUM(cp.amount), 0)) > 0.01
""")

# Count mismatches instead
cur.execute("""
    SELECT 
        COUNT(*) as count
    FROM (
        SELECT c.reserve_number
        FROM charters c
        LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
        WHERE c.cancelled = FALSE
          AND c.charter_date >= '2012-01-01'
          AND c.paid_amount > 0
        GROUP BY c.reserve_number, c.paid_amount
        HAVING ABS(c.paid_amount - COALESCE(SUM(cp.amount), 0)) > 0.01
    ) AS mismatches
""")

mismatch_count = cur.fetchone()['count']
print(f"\nPayment mismatches remaining: {mismatch_count}")

print("\n" + "="*100)

cur.close()
conn.close()
