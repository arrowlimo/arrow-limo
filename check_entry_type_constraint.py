import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get the check constraint definition
cur.execute("""
    SELECT pg_get_constraintdef(c.oid)
    FROM pg_constraint c
    WHERE c.conname = 'entry_type_ck'
""")

result = cur.fetchone()
if result:
    print(f"entry_type_ck constraint: {result[0]}")
else:
    print("Constraint not found")

# Also check what values currently exist
cur.execute("""
    SELECT DISTINCT entry_type FROM vendor_account_ledger ORDER BY entry_type
""")

print("\nExisting entry_type values:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
