import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, category
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
    AND EXTRACT(YEAR FROM transaction_date) = 2013 
    AND (description ILIKE '%Credit Memo%' OR description ILIKE '%Debit Memo%') 
    ORDER BY transaction_date, description
""")

print("\nScotia 2013 Credit/Debit Memo Transactions:\n")
print(f"{'Date':<12} | {'Description':<45} | {'Debit':<10} | {'Credit':<10} | {'Category':<25}")
print("-" * 120)
for row in cur.fetchall():
    debit = f"${row[2]:,.2f}" if row[2] else "-"
    credit = f"${row[3]:,.2f}" if row[3] else "-"
    print(f"{row[0]} | {row[1][:45]:<45} | {debit:>10} | {credit:>10} | {row[4] or 'NULL':<25}")

cur.close()
conn.close()
