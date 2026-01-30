"""Check 2014 opening to verify expected from 2013 closing."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Get first 2014 transaction
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND EXTRACT(YEAR FROM transaction_date) = 2014
    ORDER BY transaction_date ASC, transaction_id ASC 
    LIMIT 3
""")

print("First 2014 transactions:")
print("="*80)
for row in cur.fetchall():
    date, desc, debit, credit, balance = row
    debit_str = f"${debit:.2f}" if debit else "  --  "
    credit_str = f"${credit:.2f}" if credit else "  --  "
    balance_str = f"${balance:.2f}" if balance else "NULL"
    print(f"{date} | D:{debit_str:>10} | C:{credit_str:>10} | Bal:{balance_str:>10} | {desc[:40]}")

print("\n" + "="*80)
print("Expected 2014 opening: $-3,524.94 (from calculated 2013 closing)")

conn.close()
