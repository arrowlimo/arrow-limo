import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check banking_transactions
cur.execute("""SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name='banking_transactions' 
ORDER BY ordinal_position""")

print("=" * 80)
print("banking_transactions COLUMNS:")
print("=" * 80)
for col, dtype in cur.fetchall():
    print(f"{col:<40} {dtype}")

# Check payments
cur.execute("""SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name='payments' 
ORDER BY ordinal_position""")

print("\n" + "=" * 80)
print("payments COLUMNS:")
print("=" * 80)
for col, dtype in cur.fetchall():
    print(f"{col:<40} {dtype}")

# Check charters
cur.execute("""SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name='charters' 
ORDER BY ordinal_position""")

print("\n" + "=" * 80)
print("charters COLUMNS:")
print("=" * 80)
for col, dtype in cur.fetchall():
    print(f"{col:<40} {dtype}")

conn.close()
