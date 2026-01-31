"""Quick check of CIBC 1615 data by year."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date)::int as year,
        COUNT(*) as count,
        COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_balances,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY year
    ORDER BY year
""")

print("CIBC 1615 Data Status:")
print("=" * 80)
print(f"{'Year':<6} {'Transactions':<14} {'NULL Balances':<15} {'Date Range':<30}")
print("-" * 80)

for year, count, nulls, first, last in cur.fetchall():
    print(f"{year:<6} {count:<14} {nulls:<15} {first} to {last}")

cur.close()
conn.close()
