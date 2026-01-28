import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

# Find all tables that reference employees.employee_id
cur.execute("""
SELECT DISTINCT
    tc.table_name,
    kcu.column_name,
    ccu.table_name as foreign_table_name,
    ccu.column_name as foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
AND ccu.table_name = 'employees'
ORDER BY tc.table_name
""")

print("Tables with FK to employees:")
for r in cur.fetchall():
    print(f"  {r[0]:40s} | column {r[1]:20s} → employees.{r[3]}")

# Get counts
cur.execute("""
SELECT table_name, COUNT(*) FROM (
SELECT DISTINCT tc.table_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND ccu.table_name = 'employees'
) t GROUP BY table_name
""")

print("\nFK counts:")
for table, count in cur.fetchall():
    print(f"  {table:40s} | {count} constraints")
