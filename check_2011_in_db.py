import psycopg2
import os

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    database=os.getenv('DB_NAME', 'almsdata')
)
cur = conn.cursor()

# Check what we have for 2011 in database
print("="*70)
print("2011 CIBC 1615 DATA IN DATABASE")
print("="*70)
print()

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        EXTRACT(MONTH FROM transaction_date) as month,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        MIN(balance) as min_balance,
        MAX(balance) as max_balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2011
    GROUP BY year, month
    ORDER BY month
""")

results = cur.fetchall()
if results:
    for row in results:
        year, month, count, first_date, last_date, min_bal, max_bal = row
        print(f"Month {int(month):2d}: {count:3d} txns | {first_date} to {last_date} | Balance: {min_bal} to {max_bal}")
else:
    print("NO 2011 DATA IN DATABASE!")

print()
print("="*70)
print("CHECKING IF ANY 2011 DATA EXISTS:")
print("="*70)

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2011
""")

count = cur.fetchone()[0]
print(f"Total 2011 records for account 1615: {count}")

conn.close()
