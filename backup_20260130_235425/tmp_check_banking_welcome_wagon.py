import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Check banking transactions for these IDs: 60114, 60118, 80594
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit,
        credit,
        balance,
        check_number,
        category
    FROM banking_transactions 
    WHERE transaction_id IN (60114, 60118, 80594)
    ORDER BY transaction_date, transaction_id
""")

rows = cur.fetchall()

print("Banking transactions for Welcome Wagon receipts:\n")
print(f"{'TX ID':<10} {'Date':<12} {'Description':<40} {'Debit':<10} {'Credit':<10} {'Check#':<10} {'Category'}")
print('-' * 120)

for row in rows:
    tx_id, tx_date, desc, debit, credit, balance, check_num, category = row
    print(f"{tx_id:<10} {str(tx_date):<12} {desc or '':<40} {debit or 0:>9.2f} {credit or 0:>9.2f} {check_num or 'N/A':<10} {category or ''}")

cur.close()
conn.close()
