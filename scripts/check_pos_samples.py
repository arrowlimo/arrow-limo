import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)
cur = conn.cursor()

print("Sample POINT OF SALE transactions:")
cur.execute("""
    SELECT DISTINCT description 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
    AND description LIKE 'POINT OF SALE%' 
    ORDER BY description 
    LIMIT 15
""")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
