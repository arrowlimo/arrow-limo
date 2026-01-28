"""Quick check for QBO payment patterns in 2013-2015."""
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor(cursor_factory=RealDictCursor)

# Check for various QBO/import patterns
patterns = [
    '%QBO Import%',
    '%QuickBooks%', 
    '%Import%',
    '%qbo%',
    '%quickbooks%'
]

print("Checking QBO patterns in 2013-2015:\n")

for pattern in patterns:
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) as year,
            COUNT(*) as count,
            SUM(amount) as total
        FROM payments
        WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN 2013 AND 2015
        AND notes ILIKE %s
        GROUP BY EXTRACT(YEAR FROM CAST(payment_date AS timestamp))
        ORDER BY year
    """, (pattern,))
    
    results = cur.fetchall()
    if results:
        print(f"Pattern: {pattern}")
        for row in results:
            print(f"  {int(row['year'])}: {row['count']} payments (${row['total']:,.2f})")
        print()

# Check ALL payments in these years for comparison
print("\nTotal payments by year (2013-2015):")
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) as year,
        COUNT(*) as count,
        SUM(amount) as total
    FROM payments
    WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) BETWEEN 2013 AND 2015
    GROUP BY EXTRACT(YEAR FROM CAST(payment_date AS timestamp))
    ORDER BY year
""")

for row in cur.fetchall():
    print(f"  {int(row['year'])}: {row['count']} payments (${row['total']:,.2f})")

# Sample notes from 2013-2015
print("\nSample payment notes from 2013:")
cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, 
           SUBSTRING(notes, 1, 100) as note_sample
    FROM payments
    WHERE EXTRACT(YEAR FROM CAST(payment_date AS timestamp)) = 2013
    LIMIT 10
""")

for row in cur.fetchall():
    print(f"  {row['payment_id']}: {row['payment_date']} ${row['amount']:.2f} ({row['payment_method']})")
    print(f"    Note: {row['note_sample']}")

cur.close()
conn.close()
