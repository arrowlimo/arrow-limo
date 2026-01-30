import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("Checking accounts 1010 vs 903990106011:")
print('='*80)

# Check account details
cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE account_number IN ('1010', '903990106011')
    GROUP BY account_number
    ORDER BY account_number
""")

results = cur.fetchall()
for row in results:
    print(f"\nAccount: {row[0]}")
    print(f"  Transactions: {row[1]}")
    print(f"  Date range: {row[2]} to {row[3]}")
    print(f"  Total debits: ${row[4]:,.2f}" if row[4] else "  Total debits: $0.00")
    print(f"  Total credits: ${row[5]:,.2f}" if row[5] else "  Total credits: $0.00")

# Check if they have overlapping or duplicate data
print("\n" + "="*80)
print("Checking for duplicate transactions between accounts...")

cur.execute("""
    SELECT 
        a.transaction_id as id_1010,
        a.transaction_date,
        a.description,
        a.debit_amount,
        a.credit_amount,
        b.transaction_id as id_903990
    FROM banking_transactions a
    JOIN banking_transactions b ON 
        a.transaction_date = b.transaction_date
        AND COALESCE(a.debit_amount, 0) = COALESCE(b.debit_amount, 0)
        AND COALESCE(a.credit_amount, 0) = COALESCE(b.credit_amount, 0)
        AND LOWER(a.description) = LOWER(b.description)
    WHERE a.account_number = '1010'
    AND b.account_number = '903990106011'
    ORDER BY a.transaction_date
    LIMIT 10
""")

duplicates = cur.fetchall()
if duplicates:
    print(f"\nFound {len(duplicates)} potential duplicates (showing first 10):")
    for row in duplicates:
        print(f"  {row[1]} | {row[2][:50]} | ID 1010: {row[0]}, ID 903990: {row[5]}")
else:
    print("\nNo duplicates found between accounts")

# Sample transactions from each account
print("\n" + "="*80)
print("Sample transactions from account 1010:")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '1010'
    ORDER BY transaction_date
    LIMIT 10
""")

for row in cur.fetchall():
    amt = f"Debit:{row[3]:.2f}" if row[3] else f"Credit:{row[4]:.2f}"
    print(f"  {row[1]} | {row[2][:50]} | {amt}")

print("\n" + "="*80)
print("Sample transactions from account 903990106011:")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '903990106011'
    ORDER BY transaction_date
    LIMIT 10
""")

for row in cur.fetchall():
    amt = f"Debit:{row[3]:.2f}" if row[3] else f"Credit:{row[4]:.2f}"
    print(f"  {row[1]} | {row[2][:50]} | {amt}")

cur.close()
conn.close()
