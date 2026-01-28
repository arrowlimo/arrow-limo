"""
Get chart of accounts GL codes for expense categorization
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get all expense GL accounts
cur.execute("""
    SELECT 
        account_code, 
        account_name, 
        account_type
    FROM chart_of_accounts
    WHERE account_type IN ('Expense', 'Cost of Goods Sold', 'Other Expense')
    OR account_name ILIKE '%fuel%'
    OR account_name ILIKE '%vehicle%'
    OR account_name ILIKE '%insurance%'
    OR account_name ILIKE '%utilities%'
    OR account_name ILIKE '%bank%'
    ORDER BY account_code
""")

print("=" * 120)
print("CHART OF ACCOUNTS - EXPENSE GL CODES")
print("=" * 120)
print(f"{'GL Code':<15} {'GL Account Name':<60} {'Type':<30}")
print("=" * 120)

accounts = cur.fetchall()
for code, name, acct_type in accounts:
    print(f"{code or 'NULL':<15} {name or 'NULL':<60} {acct_type or 'NULL':<30}")

print(f"\n\nTotal expense accounts: {len(accounts)}")

cur.close()
conn.close()
