import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check month-by-month counts in Nov 24 backup
cur.execute("""
    SELECT 
        to_char(date_trunc('month', transaction_date), 'YYYY-MM') AS month,
        COUNT(*) AS row_count,
        MIN(transaction_date) AS first_date,
        MAX(transaction_date) AS last_date
    FROM banking_transactions_scotia_backup_20251124_221239
    WHERE account_number = '903990106011'
    AND transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
    GROUP BY 1
    ORDER BY 1;
""")

print("Nov 24 backup (banking_transactions_scotia_backup_20251124_221239):")
print("Month-by-month breakdown for 2012 account 903990106011:\n")
print(f"{'Month':<10} {'Rows':<6} {'First Date':<12} {'Last Date':<12}")
print("-" * 45)

for row in cur.fetchall():
    month, count, first, last = row
    print(f"{month:<10} {count:<6} {first}      {last}")

cur.close()
conn.close()
