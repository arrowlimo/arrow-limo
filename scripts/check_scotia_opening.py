import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Scotia Bank - First Transactions and Balance Forward:\n")

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions 
    WHERE account_number = '903990106011'
    ORDER BY transaction_date, transaction_id 
    LIMIT 15
""")

print(f"{'Date':<12} {'Description':<30} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
print("-" * 85)

for row in cur.fetchall():
    trans_id, date, desc, debit, credit, balance = row
    desc_str = (desc or '')[:28]
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    balance_str = f"${balance:,.2f}" if balance else ""
    print(f"{date} {desc_str:<30} {debit_str:>12} {credit_str:>12} {balance_str:>12}")

# Look specifically for BALANCE FORWARD
print("\n\nBalance Forward Entry:")
cur.execute("""
    SELECT transaction_id, transaction_date, description, balance
    FROM banking_transactions 
    WHERE account_number = '903990106011'
    AND description ILIKE '%balance forward%'
""")

result = cur.fetchone()
if result:
    print(f"Date: {result[1]}")
    print(f"Description: {result[2]}")
    print(f"Balance: ${result[3]:,.2f}")
else:
    print("No BALANCE FORWARD entry found")

cur.close()
conn.close()
