"""
Check what bank accounts exist and look for 1615 references
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 120)
print("BANK ACCOUNTS IN SYSTEM")
print("=" * 120)

# Check bank_accounts table
cur.execute("""
    SELECT *
    FROM bank_accounts
    LIMIT 10
""")

accounts = cur.fetchall()
if accounts:
    # Get column names
    col_names = [desc[0] for desc in cur.description]
    print(f"\nColumns: {', '.join(col_names)}\n")
    
    for row in accounts:
        print(dict(zip(col_names, row)))

# Check for account 1615 in banking_transactions
print("\n" + "=" * 120)
print("CHECKING FOR ACCOUNT 1615 IN BANKING TRANSACTIONS")
print("=" * 120)

cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE account_number LIKE '%1615%'
    OR description LIKE '%1615%'
""")

count, min_date, max_date = cur.fetchone()
print(f"Transactions mentioning 1615: {count or 0}")
if count:
    print(f"Date range: {min_date} to {max_date}")

# Check all distinct account numbers in banking_transactions
print("\n" + "=" * 120)
print("ALL DISTINCT ACCOUNT NUMBERS IN BANKING_TRANSACTIONS")
print("=" * 120)

cur.execute("""
    SELECT DISTINCT 
        account_number,
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    GROUP BY account_number
    ORDER BY txn_count DESC
""")

print(f"\n{'Account Number':<20} {'Transactions':<15} {'First Date':<15} {'Last Date':<15}")
print("-" * 120)
for acct, count, first, last in cur.fetchall():
    print(f"{acct or 'NULL':<20} {count:<15,} {str(first):<15} {str(last):<15}")

cur.close()
conn.close()

print("\n✅ Check complete")
