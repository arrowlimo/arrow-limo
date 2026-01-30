"""
Check payment import timeline - when were LMS payments imported?
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("PAYMENT IMPORT TIMELINE")
print("=" * 80)

# LMS payments (today's import)
cur.execute("""
    SELECT 
        MIN(created_at) as first_import,
        MAX(created_at) as last_import,
        COUNT(*) as total_count
    FROM payments 
    WHERE payment_key LIKE 'LMS:%'
""")

lms_import = cur.fetchone()
print(f"\nLMS Payments (payment_key LIKE 'LMS:%'):")
print(f"  First imported: {lms_import[0]}")
print(f"  Last imported: {lms_import[1]}")
print(f"  Total count: {lms_import[2]:,}")

# July 24 payments
cur.execute("""
    SELECT 
        COUNT(*) as count,
        MIN(payment_date) as earliest_payment,
        MAX(payment_date) as latest_payment
    FROM payments 
    WHERE created_at::date = '2025-07-24'
    AND payment_key NOT LIKE 'LMS:%'
    AND payment_key NOT LIKE 'LMSDEP:%'
""")

july_import = cur.fetchone()
print(f"\nJuly 24, 2025 Import (non-LMS, non-LMSDEP):")
print(f"  Total count: {july_import[0]:,}")
print(f"  Earliest payment date: {july_import[1]}")
print(f"  Latest payment date: {july_import[2]}")

# Check for specific overlap - payments that exist in both imports
cur.execute("""
    SELECT 
        COUNT(DISTINCT p1.payment_id) as duplicate_count
    FROM payments p1
    JOIN payments p2 ON 
        p1.reserve_number = p2.reserve_number 
        AND p1.amount = p2.amount
        AND p1.payment_date = p2.payment_date
    WHERE p1.payment_key LIKE 'LMS:%'
    AND p2.payment_key NOT LIKE 'LMS:%'
    AND p2.payment_key NOT LIKE 'LMSDEP:%'
    AND p2.created_at::date = '2025-07-24'
""")

overlap = cur.fetchone()
print(f"\nDuplicate payments between LMS import and July 24 import:")
print(f"  Count: {overlap[0]:,}")

# Show the date range issue
cur.execute("""
    SELECT 
        DATE(created_at) as import_date,
        COUNT(*) as payment_count,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_key LIKE 'LMS:%' 
    OR (created_at::date = '2025-07-24' AND payment_key NOT LIKE 'LMSDEP:%')
    GROUP BY DATE(created_at)
    ORDER BY import_date
""")

print(f"\nImport dates breakdown:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} payments, ${row[2]:,.2f}")

cur.close()
conn.close()
