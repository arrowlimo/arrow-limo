import psycopg2

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***',
    host='localhost'
)
cur = conn.cursor()

# Check for self-referencing columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='payments' 
    AND column_name LIKE '%related%'
    ORDER BY ordinal_position
""")
print("Related columns:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Check all FK constraints on payments
cur.execute("""
    SELECT 
        tc.constraint_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name 
    FROM information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.table_name='payments' 
    AND tc.constraint_type = 'FOREIGN KEY'
""")
print("\nForeign key constraints on payments:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} -> {row[2]}.{row[3]}")

cur.close()
conn.close()
