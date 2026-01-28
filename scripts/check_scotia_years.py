"""
Check Scotia account activity by year.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get transactions by year
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year, 
        COUNT(*) as count
    FROM banking_transactions 
    WHERE account_number = '903990106011'
    GROUP BY year 
    ORDER BY year
""")

print("Scotia Bank 903990106011 Transaction Years:")
print("=" * 60)
for row in cur.fetchall():
    year = int(row[0])
    count = row[1]
    print(f"{year}: {count:4d} transactions")

# Get overall range
cur.execute("""
    SELECT 
        MIN(transaction_date), 
        MAX(transaction_date), 
        COUNT(*) 
    FROM banking_transactions 
    WHERE account_number = '903990106011'
""")
row = cur.fetchone()
print(f"\nOverall: {row[0]} to {row[1]} ({row[2]} transactions)")

cur.close()
conn.close()
