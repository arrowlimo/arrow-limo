"""Check banking_payment_links table structure"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get columns
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_payment_links' 
    ORDER BY ordinal_position
""")
print("banking_payment_links columns:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

# Get FK constraints
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
    WHERE tc.table_name = 'banking_payment_links' 
    AND tc.constraint_type = 'FOREIGN KEY'
""")
print("\nForeign keys:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} -> {row[2]}.{row[3]}")

# Count
cur.execute("SELECT COUNT(*) FROM banking_payment_links")
print(f"\nTotal links: {cur.fetchone()[0]}")

# Check duplicates that are being deleted
cur.execute("""
    SELECT COUNT(*)
    FROM banking_payment_links
    WHERE payment_id IN (30478, 100635, 100636, 100637, 100638, 100639, 100640, 100641, 100642, 100643, 100644, 100604, 100605, 100606, 100634)
""")
print(f"Links to duplicate payments being deleted: {cur.fetchone()[0]}")

conn.close()
