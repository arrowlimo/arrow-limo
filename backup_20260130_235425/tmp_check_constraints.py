import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor()

# Get the check constraint definition
cur.execute("""
    SELECT pg_get_constraintdef(oid) 
    FROM pg_constraint 
    WHERE conrelid = 'assets'::regclass AND contype = 'c'
""")

print("Check constraints on assets table:")
for row in cur.fetchall():
    print(f"  {row[0]}")
