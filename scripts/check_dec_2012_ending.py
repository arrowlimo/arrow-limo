"""Check actual December 2012 ending balance for Scotia Bank."""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)

cur = conn.cursor()

print("="*80)
print("SCOTIA BANK DECEMBER 2012 ENDING BALANCE")
print("="*80)
print()

# Get last 15 transactions of 2012
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 15
""")

rows = cur.fetchall()

print(f"Last 15 transactions of 2012:")
print()
print(f"{'Date':<12} {'Description':<50} {'Debit':>12} {'Credit':>12} {'Balance':>15}")
print("-"*110)

for date, desc, debit, credit, balance in rows:
    desc = (desc or "")[:50]
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    bal_str = f"${balance:,.2f}" if balance else "NULL"
    print(f"{date!s:<12} {desc:<50} {debit_str:>12} {credit_str:>12} {bal_str:>15}")

print()
print("="*80)
print()

# Get the actual last balance of 2012
cur.execute("""
    SELECT transaction_date, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
""")

last_date, last_balance = cur.fetchone()
print(f"📊 Last transaction date: {last_date}")
print(f"📊 Last balance of 2012: ${last_balance:,.2f}")
print()

if abs(float(last_balance) - 952.04) < 0.01:
    print("✅ MATCHES expected ending balance of $952.04")
else:
    diff = float(last_balance) - 952.04
    print(f"❌ DOES NOT MATCH expected $952.04")
    print(f"   Difference: ${diff:,.2f}")

cur.close()
conn.close()
