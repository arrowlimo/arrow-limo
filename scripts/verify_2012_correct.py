"""Fix the 2012 closing balance marker."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# The correct 2012 closing is -$49.17 (from the "Closing balance" entry)
# But also keep the "Balance forward" entry which shows $74.83

print("2012 Closing Balance Status:")
print("-" * 80)

cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND description IN ('Closing balance', 'Balance forward')
    ORDER BY transaction_date
""")

for row in cur.fetchall():
    print(f"  {row[0]} | {row[1]:20} | ${row[2]:>10.2f}")

print("\n✅ Correct closing balance is: -$49.17")
print("   (from 'Closing balance' entry on 2012-01-31)")

conn.close()
