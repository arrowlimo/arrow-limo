import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("SQUARE DEPOSIT TRANSACTIONS IN DEBIT COLUMN")
print("(These need description changed in Excel - amounts are correct)")
print("=" * 80)

cur.execute("""
    SELECT transaction_date, description, debit_amount 
    FROM banking_transactions 
    WHERE bank_id = 1 
    AND source_file = '2014-2017 CIBC 8362.xlsx' 
    AND UPPER(description) LIKE '%SQUARE DEPOSIT%' 
    AND debit_amount IS NOT NULL 
    ORDER BY transaction_date
""")

results = cur.fetchall()
print(f"\nFound {len(results)} transactions\n")
print(f"{'Date':<15} {'Amount':<12} {'Current Description'}")
print("-" * 80)
for date, desc, debit in results:
    print(f"{str(date):<15} ${debit:>9.2f}   {desc}")

print("\n" + "=" * 80)
print("BANK DEPOSIT IN DEBIT COLUMN")
print("=" * 80)

cur.execute("""
    SELECT transaction_date, description, debit_amount 
    FROM banking_transactions 
    WHERE bank_id = 1 
    AND source_file = '2014-2017 CIBC 8362.xlsx' 
    AND UPPER(description) LIKE '%BANK DEPOSIT%'
    AND UPPER(description) NOT LIKE '%STOP%'
    AND debit_amount IS NOT NULL 
    ORDER BY transaction_date
""")

results = cur.fetchall()
print(f"\nFound {len(results)} transactions\n")
print(f"{'Date':<15} {'Amount':<12} {'Current Description'}")
print("-" * 80)
for date, desc, debit in results:
    print(f"{str(date):<15} ${debit:>9.2f}   {desc}")

print("\n" + "=" * 80)
print("BANK WITHDRAWAL IN CREDIT COLUMN")
print("=" * 80)

cur.execute("""
    SELECT transaction_date, description, credit_amount 
    FROM banking_transactions 
    WHERE bank_id = 1 
    AND source_file = '2014-2017 CIBC 8362.xlsx' 
    AND UPPER(description) LIKE '%BANK WITHDRAWAL%'
    AND UPPER(description) NOT LIKE '%STOP%'
    AND credit_amount IS NOT NULL 
    ORDER BY transaction_date
""")

results = cur.fetchall()
print(f"\nFound {len(results)} transactions\n")
print(f"{'Date':<15} {'Amount':<12} {'Current Description'}")
print("-" * 80)
for date, desc, credit in results:
    print(f"{str(date):<15} ${credit:>9.2f}   {desc}")

cur.close()
conn.close()
