import psycopg2

conn = psycopg2.connect('dbname=almsdata user=postgres password=***REMOVED*** host=localhost')
cur = conn.cursor()

cur.execute("""
    SELECT tc.table_name, kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND kcu.column_name = 'payment_id'
    AND tc.table_schema = 'public'
""")

print("Tables with foreign key references to payments.payment_id:")
for row in cur.fetchall():
    print(f"  {row[0]}.{row[1]}")

cur.close()
conn.close()
