import psycopg2
from decimal import Decimal

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)
cur = conn.cursor()

print("=" * 80)
print("SCOTIA 2013 ENDING BALANCE VERIFICATION")
print("=" * 80)

# Check 2013 opening balance (should match 2012 closing)
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date ASC, transaction_id ASC
    LIMIT 5
""")

print("\n2013 OPENING TRANSACTIONS:")
print("-" * 80)
opening_rows = cur.fetchall()
for row in opening_rows:
    date, desc, debit, credit, balance = row
    debit = float(debit) if debit else 0.0
    credit = float(credit) if credit else 0.0
    balance = float(balance) if balance else 0.0
    print(f"{date} | {desc:<30} | Debit: ${debit:>10,.2f} | Credit: ${credit:>10,.2f} | Balance: ${balance:>12,.2f}")

if opening_rows:
    first_balance = float(opening_rows[0][4]) if opening_rows[0][4] else 0.0
    print(f"\n2013 Opening Balance: ${first_balance:,.2f}")
    print(f"Expected (2012 closing): $952.04")
    if abs(first_balance - 952.04) < 0.01:
        print("✓ MATCHES 2012 closing")
    else:
        diff = first_balance - 952.04
        print(f"✗ DOES NOT MATCH - Difference: ${diff:,.2f}")

# Check 2013 ending balance
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 15
""")

print("\n" + "=" * 80)
print("LAST 15 TRANSACTIONS OF 2013:")
print("-" * 80)
rows = cur.fetchall()
for row in rows:
    date, desc, debit, credit, balance = row
    debit = float(debit) if debit else 0.0
    credit = float(credit) if credit else 0.0
    balance = float(balance) if balance else 0.0
    print(f"{date} | {desc:<30} | Debit: ${debit:>10,.2f} | Credit: ${credit:>10,.2f} | Balance: ${balance:>12,.2f}")

if rows:
    last_date = rows[0][0]
    last_balance = float(rows[0][4]) if rows[0][4] else 0.0
    expected_balance = 6404.87
    
    print("\n" + "=" * 80)
    print("2013 ENDING BALANCE ANALYSIS:")
    print("-" * 80)
    print(f"Last transaction date: {last_date}")
    print(f"Last balance:          ${last_balance:,.2f}")
    print(f"Expected balance:      ${expected_balance:,.2f}")
    print(f"Difference:            ${last_balance - expected_balance:,.2f}")
    
    if abs(last_balance - expected_balance) < 0.01:
        print("✓ MATCHES expected")
    else:
        print("✗ DOES NOT MATCH expected")

# Get 2013 transaction count
cur.execute("""
    SELECT COUNT(*) FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2013
""")
count = cur.fetchone()[0]
print(f"\nTotal 2013 transactions: {count:,}")

cur.close()
conn.close()
