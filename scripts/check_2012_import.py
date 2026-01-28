"""Check 2012 imported data."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
""")

print("2012 Transactions Imported:")
print("=" * 100)
for date, desc, debit, credit, bal in cur.fetchall():
    debit_str = f"${float(debit):>10.2f}" if debit else "       -    "
    credit_str = f"${float(credit):>10.2f}" if credit else "       -    "
    bal_str = f"${float(bal):>10.2f}" if bal else "       -    "
    print(f"{date} | D:{debit_str} | C:{credit_str} | Bal:{bal_str} | {desc}")

cur.close()
conn.close()
