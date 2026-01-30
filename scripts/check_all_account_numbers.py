"""Check what account numbers exist in banking_transactions."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Get all distinct account numbers with counts
cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as transactions,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest,
        ROUND(SUM(COALESCE(debit_amount, 0))::numeric, 2) as total_debits,
        ROUND(SUM(COALESCE(credit_amount, 0))::numeric, 2) as total_credits
    FROM banking_transactions
    GROUP BY account_number
    ORDER BY account_number
""")

print("Account numbers in banking_transactions:\n")
for row in cur.fetchall():
    acct, count, earliest, latest, debits, credits = row
    print(f"Account: {acct}")
    print(f"  Transactions: {count}")
    print(f"  Date Range: {earliest} to {latest}")
    print(f"  Total Debits: ${debits:,.2f}")
    print(f"  Total Credits: ${credits:,.2f}")
    print()

# Check for 2012 data specifically
print("\n2012 data by account:")
cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as transactions,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY account_number
    ORDER BY account_number
""")

for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} transactions from {row[2]} to {row[3]}")

cur.close()
conn.close()
