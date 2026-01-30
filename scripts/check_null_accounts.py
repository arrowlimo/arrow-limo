"""Check NULL account_name records in 2025"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
cur = conn.cursor()

# Check records with NULL account_name
cur.execute("""
    SELECT id, date, account_name, account, account_full_name, debit, credit, name, memo_description
    FROM general_ledger
    WHERE account_name IS NULL 
    AND EXTRACT(YEAR FROM date) = 2025
    ORDER BY date
    LIMIT 20
""")

print("Sample records with NULL account_name in 2025:")
print("=" * 140)
for row in cur.fetchall():
    gl_id, date, account_name, account, account_full, debit, credit, name, memo = row
    amount = debit if debit else credit
    memo_short = memo[:50] if memo else None
    print(f"ID {gl_id}: {date} | account_name={account_name} | account={account} | full={account_full} | ${amount} | name={name}")

# Check if these records have account field populated
print("\n" + "=" * 140)
print("Checking 'account' field usage...")
cur.execute("""
    SELECT id, date, account, account_full_name, debit, credit, name
    FROM general_ledger
    WHERE account_name IS NULL 
    AND EXTRACT(YEAR FROM date) = 2025
    LIMIT 10
""")

for row in cur.fetchall():
    gl_id, date, account, account_full, debit, credit, name = row
    amount = debit if debit else credit
    print(f"ID {gl_id}: {date} | account={account} | account_full_name={account_full} | ${amount} | name={name}")

conn.close()
