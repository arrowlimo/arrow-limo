"""Check last 2013 transactions."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date DESC, transaction_id DESC 
    LIMIT 10
""")

print("Last 10 transactions of 2013:")
print("="*80)
for row in cur.fetchall():
    date, desc, debit, credit = row
    debit_str = f"${debit:.2f}" if debit else "  --  "
    credit_str = f"${credit:.2f}" if credit else "  --  "
    print(f"{date} | D:{debit_str:>10} | C:{credit_str:>10} | {desc[:50]}")

print("\n" + "="*80)
print("Calculated 2013 closing: $-3,524.94")
print("Actual 2014 opening:     $-3,499.56")
print("Difference:              $   25.38")
print("\nPossible causes:")
print("  1. Missing 2013 transaction(s)")
print("  2. Year-end adjustment/correction")
print("  3. Error in 2014 opening balance import")

conn.close()
