import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Get the exact source of transaction 60118
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        category,
        source_file,
        is_nsf_charge
    FROM banking_transactions 
    WHERE transaction_id = 60118
""")

row = cur.fetchone()

print("Transaction 60118 details:\n")
print("="*100)
if row:
    tx_id, tx_date, desc, debit, credit, balance, cat, source, is_nsf = row
    print(f"Transaction ID: {tx_id}")
    print(f"Date: {tx_date}")
    print(f"Description: '{desc}'")
    print(f"Debit: ${debit:.2f}" if debit else "Debit: N/A")
    print(f"Credit: ${credit:.2f}" if credit else "Credit: N/A")
    print(f"Balance: ${balance:.2f}" if balance else "Balance: N/A")
    print(f"Category: {cat}")
    print(f"Source file: {source}")
    print(f"Is NSF Charge flag: {is_nsf}")
    
print("\n" + "="*100)
print("\nLooking at surrounding transactions on March 14, 2012:\n")

# Get context around this transaction
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        category
    FROM banking_transactions 
    WHERE transaction_date = '2012-03-14'
        AND account_number = '0228362'
    ORDER BY balance DESC
""")

rows = cur.fetchall()

print(f"{'TX ID':<10} {'Description':<60} {'Debit':<12} {'Credit':<12} {'Balance':<12} {'Category'}")
print('-' * 130)

for r in rows:
    tx_id, tx_date, desc, debit, credit, balance, cat = r
    debit_str = f"${debit:.2f}" if debit else ""
    credit_str = f"${credit:.2f}" if credit else ""
    balance_str = f"${balance:.2f}" if balance else ""
    print(f"{tx_id:<10} {desc[:60]:<60} {debit_str:>11} {credit_str:>11} {balance_str:>11} {cat}")

cur.close()
conn.close()

print("\n" + "="*100)
print("\nBased on the bank statement PDF you're looking at:")
print("What do you see for March 14 and March 19/20 related to Welcome Wagon / Check 215?")
print("="*100)
