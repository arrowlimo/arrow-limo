import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check transactions 55194, 55195 (the "RETURNED NSF CHEQUE" ones)
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions 
    WHERE transaction_id IN (55194, 55195, 55188, 55189)
    ORDER BY transaction_id
""")

print("Checking specific NSF transactions from receipts:")
print("ID       | Date       | Debit      | Credit     | Balance    | Description")
print("-" * 100)
for r in cur.fetchall():
    debit = r[3] if r[3] else 0
    credit = r[4] if r[4] else 0
    balance = r[5] if r[5] else 0
    print(f"{r[0]:<8} | {r[1]} | ${debit:>9.2f} | ${credit:>9.2f} | ${balance:>9.2f} | {r[2][:40]}")

# Now look for ALL transactions with these exact amounts in Oct-Nov
print("\n" + "=" * 100)
print("All transactions with amounts $1,900.50 or $2,525.25 in Oct-Nov 2012:")
print("=" * 100)

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions 
    WHERE account_number = '903990106011'
        AND transaction_date BETWEEN '2012-10-01' AND '2012-11-30'
        AND (ABS(debit_amount - 1900.50) < 0.01 OR ABS(credit_amount - 1900.50) < 0.01
             OR ABS(debit_amount - 2525.25) < 0.01 OR ABS(credit_amount - 2525.25) < 0.01)
    ORDER BY transaction_date, transaction_id
""")

print("ID       | Date       | Debit      | Credit     | Description")
print("-" * 100)
for r in cur.fetchall():
    debit = r[3] if r[3] else 0
    credit = r[4] if r[4] else 0
    print(f"{r[0]:<8} | {r[1]} | ${debit:>9.2f} | ${credit:>9.2f} | {r[2][:50]}")

cur.close()
conn.close()
