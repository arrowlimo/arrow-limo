"""Verify the 2012 closing balance entry exists correctly."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Check for Closing balance entry
cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND description LIKE '%Closing%' 
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")

closing = cur.fetchall()
print("\nClosing balance entries:")
for row in closing:
    print(f"  {row[0]} | {row[1]} | Balance: ${row[2]}")

# Check last transaction by date (the problematic query)
cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date DESC 
    LIMIT 1
""")

last = cur.fetchone()
print(f"\nLast transaction by date: {last[0]} | {last[1]} | Balance: ${last[2]}")

# Check actual last chronological transaction (by proper ordering)
cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND description = 'Closing balance'
""")

proper_closing = cur.fetchone()
if proper_closing:
    print(f"\n✅ Proper closing balance found: {proper_closing[0]} | ${proper_closing[2]}")
    if float(proper_closing[2]) == -49.17:
        print("✅ Amount matches expected: -$49.17")
    else:
        print(f"❌ Amount mismatch: expected -$49.17, got ${proper_closing[2]}")
else:
    print("\n❌ No 'Closing balance' entry found!")

conn.close()
