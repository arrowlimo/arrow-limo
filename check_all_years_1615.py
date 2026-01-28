import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

cur.execute('''
    SELECT 
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        ROUND(SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END)::numeric, 2) as total_debits,
        ROUND(SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END)::numeric, 2) as total_credits
    FROM banking_transactions
    WHERE account_number = '1615'
    GROUP BY EXTRACT(YEAR FROM transaction_date)
    ORDER BY year
''')

print("Account 1615 Banking Data Summary:\n")
print(f"{'Year':<6} {'Count':<8} {'First Date':<12} {'Last Date':<12} {'Debits':<12} {'Credits':<12}")
print("-" * 78)

for row in cur.fetchall():
    year, count, first_date, last_date, debits, credits = row
    print(f"{int(year):<6} {count:<8} {str(first_date):<12} {str(last_date):<12} ${float(debits):<11.2f} ${float(credits):<11.2f}")

cur.close()
conn.close()
