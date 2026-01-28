import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check actual charters table schema
cur.execute("""
    SELECT column_name, data_type, is_nullable 
    FROM information_schema.columns 
    WHERE table_name = 'charters' 
    ORDER BY ordinal_position
""")

print("=" * 70)
print("CHARTERS TABLE ACTUAL SCHEMA")
print("=" * 70)
print(f"{'Column Name':<30} {'Data Type':<20} {'Nullable'}")
print("-" * 70)

for row in cur.fetchall():
    print(f"{row[0]:<30} {row[1]:<20} {row[2]}")

print()
print("MISSING COLUMNS IN BROKEN CODE:")
print("  - customer_name (code tries to use this)")
print("  - phone (code tries to use this)")  
print("  - email (code tries to use this)")
print()
print("LIKELY SOLUTION:")
print("  - Charters link to clients via client_id or account_number")
print("  - Customer info stored in clients table, not charters")
print("  - Dialog should select/create client first, then create charter")

conn.close()
