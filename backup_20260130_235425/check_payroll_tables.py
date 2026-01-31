import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check for payroll-related tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%payroll%' OR table_name LIKE '%pay%'
    ORDER BY table_name
""")

print("Payroll-related tables:")
for row in cur.fetchall():
    print(f"  {row[0]}")

# Check employee_payroll if it exists
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'employee_payroll'
""")

if cur.fetchone():
    print("\nemployee_payroll columns:")
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'employee_payroll' 
        ORDER BY ordinal_position
    """)
    for row in cur.fetchall():
        print(f"  {row[0]} ({row[1]})")

cur.close()
conn.close()
