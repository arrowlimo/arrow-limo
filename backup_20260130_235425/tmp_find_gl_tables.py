import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Find GL/Account related tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND (table_name LIKE '%account%' 
         OR table_name LIKE '%gl%'
         OR table_name LIKE '%chart%'
         OR table_name LIKE '%expense%')
    ORDER BY table_name
""")

tables = [r[0] for r in cur.fetchall()]

print("Tables related to GL/Accounts/Chart:\n")
for t in tables:
    print(f"  - {t}")

print("\n" + "="*100)
print("\nLet me check what columns are in these tables...\n")

for table in tables:
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    
    cols = cur.fetchall()
    print(f"\nTable: {table}")
    print(f"  Columns: {', '.join([c[0] for c in cols])}")

cur.close()
conn.close()
