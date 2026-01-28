"""Quick check of missing vendor names after import"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

# Check 2025 missing names
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE (name IS NULL OR name = '' OR name = 'nan') 
    AND EXTRACT(YEAR FROM date) = 2025
""")
missing_2025 = cur.fetchone()[0]

# Check total missing names
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE (name IS NULL OR name = '' OR name = 'nan')
""")
total_missing = cur.fetchone()[0]

# Check records with supplier data now
cur.execute("""
    SELECT COUNT(*) 
    FROM general_ledger 
    WHERE supplier IS NOT NULL AND supplier != '' AND supplier != 'nan'
""")
with_supplier = cur.fetchone()[0]

print(f"Missing names in 2025: {missing_2025}")
print(f"Total missing names: {total_missing}")
print(f"Records with supplier data: {with_supplier}")

conn.close()
