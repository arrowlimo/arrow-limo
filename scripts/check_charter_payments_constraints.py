import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check constraints
cur.execute("""
    SELECT constraint_name, constraint_type 
    FROM information_schema.table_constraints 
    WHERE table_name = 'charter_payments'
""")

print("charter_payments constraints:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check unique constraints
cur.execute("""
    SELECT column_name
    FROM information_schema.key_column_usage
    WHERE table_name = 'charter_payments' AND constraint_name LIKE '%unique%'
""")

print("\nUnique columns:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
