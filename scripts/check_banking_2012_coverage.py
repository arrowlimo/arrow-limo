"""Check banking_transactions coverage for 2012 dates in QB file."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check overall 2012 coverage
cur.execute("""
    SELECT 
        COUNT(*) as total_transactions,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_debits,
        ROUND(SUM(COALESCE(credit_amount, 0))::numeric, 2) as total_credits
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

result = cur.fetchone()
print("2012 Banking Transactions (Account 0228362):")
print(f"  Total: {result[0]}")
print(f"  Date Range: {result[1]} to {result[2]}")
print(f"  Total Debits: ${result[3]:,.2f}")
print(f"  Total Credits: ${result[4]:,.2f}")

# Check specific QB date range (May-July 2012)
cur.execute("""
    SELECT 
        COUNT(*) as total_transactions,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_debits
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND transaction_date BETWEEN '2012-05-01' AND '2012-07-31'
""")

result = cur.fetchone()
print(f"\nMay-July 2012 Coverage:")
print(f"  Total: {result[0]}")
print(f"  Total Debits: ${result[1]:,.2f}")

# Sample some specific dates from QB file
test_dates = ['2012-05-18', '2012-06-21', '2012-06-22', '2012-06-23', '2012-07-04', '2012-07-09']
for test_date in test_dates:
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2)
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND transaction_date = %s
    """, (test_date,))
    count, total = cur.fetchone()
    print(f"  {test_date}: {count} transactions, ${total or 0:,.2f} debits")

cur.close()
conn.close()
