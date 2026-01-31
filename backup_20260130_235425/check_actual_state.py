"""Check actual state of balances across all years."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

for year in [2012, 2013, 2014, 2015, 2016, 2017]:
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_count,
            COUNT(CASE WHEN balance IS NOT NULL THEN 1 END) as filled_count,
            MIN(balance) as min_bal,
            MAX(balance) as max_bal
        FROM banking_transactions
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = %s
    """, (year,))
    
    row = cur.fetchone()
    total, null_count, filled_count, min_bal, max_bal = row
    
    print(f"{year}: {total} txns | {filled_count} filled | {null_count} NULL | Range: ${min_bal} to ${max_bal}")

print("\n" + "="*80)
print("Checking 2012 closing:")
cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND description IN ('Closing balance', 'Balance forward')
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
for row in cur.fetchall():
    print(f"  {row[0]} | {row[1]} | ${row[2]}")

conn.close()
