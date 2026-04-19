import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# First check what columns exist in unified_general_ledger
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'unified_general_ledger'
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print("COLUMNS:", cols)

# Check what status values exist
cur.execute("SELECT DISTINCT status, COUNT(*) FROM unified_general_ledger GROUP BY status ORDER BY COUNT(*) DESC LIMIT 20")
print("\nSTATUS COUNTS:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
