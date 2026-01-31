import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Get all columns from banking_transactions
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    ORDER BY ordinal_position
""")

columns = [r[0] for r in cur.fetchall()]
print("Columns in banking_transactions:")
print(', '.join(columns))
print("\n" + "="*80 + "\n")

# Query with SELECT *
cur.execute("""
    SELECT * 
    FROM banking_transactions 
    WHERE transaction_id IN (60114, 60118, 80594)
    ORDER BY transaction_date, transaction_id
""")

rows = cur.fetchall()

print(f"Found {len(rows)} banking transactions:\n")

for row in rows:
    print(f"Transaction ID: {row[0]}")
    for i, col in enumerate(columns):
        if row[i] is not None and row[i] != '':
            print(f"  {col}: {row[i]}")
    print()

cur.close()
conn.close()
