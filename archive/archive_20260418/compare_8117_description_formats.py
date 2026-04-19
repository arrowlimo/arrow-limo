import psycopg2
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="ArrowLimousine"
)

cursor = conn.cursor()

print("=" * 80)
print("2012 CIBC 8117 Transaction Descriptions")
print("=" * 80)

cursor.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        category
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
""")

transactions_2012 = cursor.fetchall()

print(f"\nTotal 2012 transactions: {len(transactions_2012)}\n")
print("Sample of 2012 descriptions:")
print("-" * 80)

for txn in transactions_2012[:30]:  # Show first 30
    date, desc, debit, credit, category = txn
    amount = credit if credit else -debit if debit else 0
    print(f"{date.strftime('%Y-%m-%d')} | ${amount:>10.2f} | {desc}")

print("\n" + "=" * 80)
print("2018 CIBC 8117 Transaction Descriptions (for comparison)")
print("=" * 80)

cursor.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        category
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2018
    ORDER BY transaction_date
    LIMIT 30
""")

transactions_2018 = cursor.fetchall()

print(f"\nTotal transactions shown: {len(transactions_2018)}\n")
print("Sample of 2018 descriptions:")
print("-" * 80)

for txn in transactions_2018:
    date, desc, debit, credit, category = txn
    amount = credit if credit else -debit if debit else 0
    print(f"{date.strftime('%Y-%m-%d')} | ${amount:>10.2f} | {desc}")

print("\n" + "=" * 80)
print("DESCRIPTION FORMAT ANALYSIS")
print("=" * 80)

# Get unique description patterns
cursor.execute("""
    SELECT 
        substring(description from '^[^0-9]*') as pattern,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY pattern
    ORDER BY count DESC
""")

patterns_2012 = cursor.fetchall()

print("\n2012 Description Patterns (most common):")
for pattern, count in patterns_2012[:10]:
    print(f"  '{pattern.strip()}' - {count} occurrences")

cursor.execute("""
    SELECT 
        substring(description from '^[^0-9]*') as pattern,
        COUNT(*) as count
    FROM banking_transactions
    WHERE account_number = '3648117'
    AND EXTRACT(YEAR FROM transaction_date) = 2018
    GROUP BY pattern
    ORDER BY count DESC
    LIMIT 10
""")

patterns_2018 = cursor.fetchall()

print("\n2018 Description Patterns (most common):")
for pattern, count in patterns_2018:
    print(f"  '{pattern.strip()}' - {count} occurrences")

cursor.close()
conn.close()
