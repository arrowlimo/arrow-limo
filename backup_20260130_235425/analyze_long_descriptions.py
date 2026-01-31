import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)
cur = conn.cursor()

print("=" * 80)
print("ANALYZING SCOTIA BANK DESCRIPTIONS FOR CLEANUP OPPORTUNITIES")
print("=" * 80)

# Get all Scotia transactions with descriptions longer than 40 characters
cur.execute("""
    SELECT 
        description,
        COUNT(*) as count,
        LENGTH(description) as len
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND LENGTH(description) > 40
    GROUP BY description
    ORDER BY count DESC, len DESC
    LIMIT 50
""")

print("\nTOP 50 LONG DESCRIPTIONS (by frequency):")
print("-" * 80)
rows = cur.fetchall()
for desc, count, length in rows:
    print(f"{count:>4} | Len {length:>3} | {desc}")

# Check for common patterns
print("\n" + "=" * 80)
print("PATTERN ANALYSIS:")
print("-" * 80)

patterns = [
    ("PURCHASE", "SELECT COUNT(*) FROM banking_transactions WHERE account_number = '903990106011' AND description LIKE '%PURCHASE%'"),
    ("CHEQUE", "SELECT COUNT(*) FROM banking_transactions WHERE account_number = '903990106011' AND description LIKE '%CHEQUE%'"),
    ("Bill Pmt", "SELECT COUNT(*) FROM banking_transactions WHERE account_number = '903990106011' AND description LIKE '%Bill Pmt%'"),
    ("PRE-AUTH", "SELECT COUNT(*) FROM banking_transactions WHERE account_number = '903990106011' AND description LIKE '%PRE-AUTH%'"),
    ("POINT OF SALE", "SELECT COUNT(*) FROM banking_transactions WHERE account_number = '903990106011' AND description LIKE '%POINT OF SALE%'"),
    ("Card numbers", "SELECT COUNT(*) FROM banking_transactions WHERE account_number = '903990106011' AND description ~ '\\d{4}\\*+\\d{3}'"),
]

for pattern_name, query in patterns:
    cur.execute(query)
    count = cur.fetchone()[0]
    if count > 0:
        print(f"{pattern_name:.<30} {count:>5} transactions")

# Show sample of each pattern
print("\n" + "=" * 80)
print("SAMPLE TRANSACTIONS BY PATTERN:")
print("-" * 80)

# PURCHASE transactions
print("\nPURCHASE transactions (first 10):")
cur.execute("""
    SELECT DISTINCT description
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND description LIKE '%PURCHASE%'
    ORDER BY description
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row[0]}")

# CHEQUE transactions
print("\nCHEQUE transactions (first 10):")
cur.execute("""
    SELECT DISTINCT description
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND description LIKE '%CHEQUE%'
    ORDER BY description
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row[0]}")

# Bill payment transactions
print("\nBill Pmt transactions (first 10):")
cur.execute("""
    SELECT DISTINCT description
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND description LIKE '%Bill Pmt%'
    ORDER BY description
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
