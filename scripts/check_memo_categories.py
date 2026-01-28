import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT description, category, COUNT(*) 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
    AND EXTRACT(YEAR FROM transaction_date) = 2013 
    AND (description ILIKE '%Credit Memo%' OR description ILIKE '%Debit Memo%') 
    GROUP BY description, category 
    ORDER BY description
""")

print("\nScotia 2013 Credit/Debit Memo Categories:\n")
print(f"{'Description':<60} | {'Category':<30} | Count")
print("-" * 100)
for row in cur.fetchall():
    print(f"{row[0][:60]:<60} | {row[1] or 'NULL':<30} | {row[2]:3d}")

cur.close()
conn.close()
