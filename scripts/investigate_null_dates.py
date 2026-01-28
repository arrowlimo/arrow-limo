"""Investigate charters with NULL charter_date - shouldn't exist if from LMS"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

# Find all charters with NULL charter_date
print(f"\n{'='*80}")
print(f"CHARTERS WITH NULL charter_date:")
print(f"{'='*80}")
cur.execute("""
    SELECT 
        c.reserve_number,
        c.booking_status,
        c.total_amount_due,
        c.created_at,
        c.updated_at,
        cl.company_name,
        cl.client_name
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.charter_date IS NULL
    ORDER BY c.created_at DESC
""")

rows = cur.fetchall()
print(f"Found {len(rows)} charters with NULL charter_date\n")

if rows:
    for row in rows:
        res, status, total, created, updated, company, client = row
        client_name = company or client or "Unknown"
        print(f"Reserve: {res}")
        print(f"  Status: {status}")
        print(f"  Client: {client_name}")
        print(f"  Total: ${total:.2f}")
        print(f"  Created: {created}")
        print(f"  Updated: {updated}")
        print()

# Check if these are all recent (created in desktop app) or old (import issues)
print(f"\n{'='*80}")
print(f"ANALYSIS:")
print(f"{'='*80}")

cur.execute("""
    SELECT 
        COUNT(*) as total_null,
        MIN(created_at) as earliest,
        MAX(created_at) as latest
    FROM charters 
    WHERE charter_date IS NULL
""")

total_null, earliest, latest = cur.fetchone()
print(f"Total NULL dates: {total_null}")
print(f"Date range: {earliest} to {latest}")

# Check status breakdown
print(f"\n{'='*80}")
print(f"STATUS BREAKDOWN:")
print(f"{'='*80}")
cur.execute("""
    SELECT booking_status, COUNT(*) 
    FROM charters 
    WHERE charter_date IS NULL
    GROUP BY booking_status
    ORDER BY COUNT(*) DESC
""")

for status, count in cur.fetchall():
    print(f"  {status}: {count}")

# Check total charters for comparison
cur.execute("SELECT COUNT(*) FROM charters")
total_charters = cur.fetchone()[0]
print(f"\n{'='*80}")
print(f"CONTEXT:")
print(f"{'='*80}")
print(f"Total charters in database: {total_charters:,}")
print(f"Charters with NULL date: {total_null} ({100*total_null/total_charters:.2f}%)")

cur.close()
conn.close()
