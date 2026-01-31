import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor()
cur.execute("""
    SELECT constraint_name, constraint_definition 
    FROM information_schema.constraint_column_usage ccu
    JOIN information_schema.table_constraints tc 
        ON ccu.constraint_name = tc.constraint_name
    WHERE ccu.table_name = 'assets' AND constraint_name LIKE '%status%'
""")
results = cur.fetchall()
if results:
    for row in results:
        print(f"Constraint: {row[0]}")
        print(f"Definition: {row[1]}")
else:
    # Check the check constraint directly
    cur.execute("""
        SELECT pg_get_constraintdef(oid) 
        FROM pg_constraint 
        WHERE conrelid = 'assets'::regclass AND conname LIKE '%status%'
    """)
    for row in cur.fetchall():
        print(f"Check: {row[0]}")
