"""Check 2013 opening balance to verify continuity from 2012."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Get 2012 closing
cur.execute("""
    SELECT transaction_date, description, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND description = 'Closing balance'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
""")
closing_2012 = cur.fetchone()

# Get first 5 transactions of 2013
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance 
    FROM banking_transactions 
    WHERE account_number = '1615' 
    AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date ASC, transaction_id ASC 
    LIMIT 5
""")
first_2013 = cur.fetchall()

print("2012 Closing Balance:")
if closing_2012:
    print(f"  {closing_2012[0]} | {closing_2012[1]} | ${closing_2012[2]}")
else:
    print("  NOT FOUND")

print("\n2013 First Transactions:")
print("="*80)
for row in first_2013:
    date, desc, debit, credit, balance = row
    debit_str = f"${debit:.2f}" if debit else "  --  "
    credit_str = f"${credit:.2f}" if credit else "  --  "
    balance_str = f"${balance:.2f}" if balance else "NULL"
    print(f"{date} | D:{debit_str:>10} | C:{credit_str:>10} | Bal:{balance_str:>10} | {desc[:40]}")

print("\n" + "="*80)
if closing_2012 and first_2013:
    expected_opening = float(closing_2012[2])
    if first_2013[0][4] is None:
        print("⚠️  2013 opening balance is NULL - needs calculation")
        print(f"    Expected opening: ${expected_opening:.2f} (from 2012 closing)")
    else:
        actual_opening = float(first_2013[0][4])
        if abs(actual_opening - expected_opening) < 0.01:
            print(f"✅ Balance continuity OK: 2012 close (${expected_opening:.2f}) → 2013 open (${actual_opening:.2f})")
        else:
            print(f"❌ Balance mismatch!")
            print(f"    2012 closing: ${expected_opening:.2f}")
            print(f"    2013 opening: ${actual_opening:.2f}")
            print(f"    Difference: ${actual_opening - expected_opening:.2f}")

conn.close()
