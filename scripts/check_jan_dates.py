import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT DISTINCT transaction_date 
    FROM banking_transactions 
    WHERE account_number='903990106011' 
    AND EXTRACT(YEAR FROM transaction_date)=2013 
    AND EXTRACT(MONTH FROM transaction_date)=1 
    ORDER BY transaction_date
""")

print("\nJanuary 2013 dates in database:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.execute("""
    SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions 
    WHERE account_number='903990106011' 
    AND EXTRACT(YEAR FROM transaction_date)=2013 
    AND EXTRACT(MONTH FROM transaction_date)=1
""")
count, debits, credits = cur.fetchone()
print(f"\nTotal: {count} transactions, ${debits:,.2f} debits, ${credits:,.2f} credits")
