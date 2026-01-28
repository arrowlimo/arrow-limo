import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost"
)
cur = conn.cursor()

print("Descriptions with 67TH ST or NORTH HILL:")
cur.execute("""
    SELECT DISTINCT description 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
    AND (description LIKE '%67TH ST%' OR description LIKE '%NORTH HILL%')
    ORDER BY description 
    LIMIT 20
""")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
