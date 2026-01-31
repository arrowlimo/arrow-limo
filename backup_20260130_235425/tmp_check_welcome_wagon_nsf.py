import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Find transactions around March 2012 for check 215 Welcome Wagon
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        check_number,
        category,
        is_nsf_charge,
        reconciliation_status
    FROM banking_transactions 
    WHERE (description ILIKE '%welcome wagon%' 
       OR (check_number = '215' AND transaction_date BETWEEN '2012-03-01' AND '2012-04-30'))
       AND account_number = '0228362'
    ORDER BY transaction_date, transaction_id
""")

rows = cur.fetchall()

print(f"Check #215 Welcome Wagon transactions (March-April 2012):\n")
print(f"{'TX ID':<10} {'Date':<12} {'Description':<55} {'Debit':<12} {'Credit':<12} {'Balance':<12} {'NSF?'}")
print('-' * 150)

for row in rows:
    tx_id, tx_date, desc, debit, credit, balance, check_num, category, is_nsf, status = row
    debit_str = f"{debit:.2f}" if debit else ""
    credit_str = f"{credit:.2f}" if credit else ""
    balance_str = f"{balance:.2f}" if balance else ""
    nsf_flag = "YES" if is_nsf else ""
    print(f"{tx_id:<10} {str(tx_date):<12} {desc[:55]:<55} {debit_str:>11} {credit_str:>11} {balance_str:>11} {nsf_flag}")

print(f"\nTotal: {len(rows)} transactions")

# Also look for NSF fees around that time
print("\n" + "="*150)
print("\nNSF-related transactions in March 2012:\n")

cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        category,
        is_nsf_charge
    FROM banking_transactions 
    WHERE transaction_date BETWEEN '2012-03-01' AND '2012-03-31'
      AND (description ILIKE '%nsf%' 
           OR description ILIKE '%returned%' 
           OR description ILIKE '%dishon%'
           OR is_nsf_charge = true)
      AND account_number = '0228362'
    ORDER BY transaction_date, transaction_id
""")

nsf_rows = cur.fetchall()

print(f"{'TX ID':<10} {'Date':<12} {'Description':<60} {'Debit':<12} {'Credit':<12} {'NSF?'}")
print('-' * 150)

for row in nsf_rows:
    tx_id, tx_date, desc, debit, credit, balance, category, is_nsf = row
    debit_str = f"{debit:.2f}" if debit else ""
    credit_str = f"{credit:.2f}" if credit else ""
    nsf_flag = "YES" if is_nsf else ""
    print(f"{tx_id:<10} {str(tx_date):<12} {desc[:60]:<60} {debit_str:>11} {credit_str:>11} {nsf_flag}")

print(f"\nTotal NSF transactions: {len(nsf_rows)}")

cur.close()
conn.close()
