"""Quick check for charter 019637 date issue"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Check charter 019637
cur.execute("""
    SELECT reserve_number, charter_date, client_id, booking_status, 
           total_amount_due, created_at, updated_at
    FROM charters 
    WHERE reserve_number = '019637'
""")

row = cur.fetchone()
if row:
    print(f"\n{'='*60}")
    print(f"Charter 019637 Database Values:")
    print(f"{'='*60}")
    print(f"Reserve Number: {row[0]}")
    print(f"Charter Date: {row[1]} (type: {type(row[1])})")
    print(f"Client ID: {row[2]}")
    print(f"Status: {row[3]}")
    print(f"Total Due: ${row[4]:.2f}")
    print(f"Created At: {row[5]}")
    print(f"Updated At: {row[6]}")
else:
    print("Charter 019637 not found!")

# Check for other charters with dates in year 1752
print(f"\n{'='*60}")
print(f"Checking for other charters with year 1752:")
print(f"{'='*60}")
cur.execute("""
    SELECT reserve_number, charter_date, booking_status
    FROM charters 
    WHERE EXTRACT(YEAR FROM charter_date) = 1752
    ORDER BY reserve_number
    LIMIT 20
""")

rows = cur.fetchall()
if rows:
    print(f"Found {len(rows)} charters with year 1752:")
    for r in rows:
        print(f"  {r[0]}: {r[1]} ({r[2]})")
else:
    print("No charters found with year 1752")

# Check for charters with suspiciously old dates (before 2000)
print(f"\n{'='*60}")
print(f"Checking for charters before year 2000:")
print(f"{'='*60}")
cur.execute("""
    SELECT COUNT(*), MIN(charter_date), MAX(charter_date)
    FROM charters 
    WHERE charter_date < '2000-01-01'
""")

count, min_date, max_date = cur.fetchone()
print(f"Count: {count}")
print(f"Earliest: {min_date}")
print(f"Latest (before 2000): {max_date}")

cur.close()
conn.close()
