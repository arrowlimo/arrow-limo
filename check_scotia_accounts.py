import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check all accounts in banking_transactions
cur.execute('''
    SELECT DISTINCT account_number FROM banking_transactions ORDER BY account_number
''')

print("All accounts in banking_transactions table:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

print("\n" + "=" * 80)

# Get Scotia accounts (903990106011 is Scotia, also check for similar patterns)
cur.execute('''
    SELECT 
        account_number,
        EXTRACT(YEAR FROM transaction_date) as year,
        COUNT(*) as count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        ROUND(SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END)::numeric, 2) as total_debits,
        ROUND(SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END)::numeric, 2) as total_credits
    FROM banking_transactions
    WHERE account_number LIKE '%9039%' OR account_number LIKE '%903%'
    GROUP BY account_number, EXTRACT(YEAR FROM transaction_date)
    ORDER BY account_number, year
''')

print("\nScotia Bank Account Summary (903990106011):\n")
print(f"{'Account':<15} {'Year':<6} {'Count':<8} {'First Date':<12} {'Last Date':<12} {'Debits':<12} {'Credits':<12}")
print("-" * 97)

for row in cur.fetchall():
    account, year, count, first_date, last_date, debits, credits = row
    print(f"{account:<15} {int(year):<6} {count:<8} {str(first_date):<12} {str(last_date):<12} ${float(debits):<11.2f} ${float(credits):<11.2f}")

cur.close()
conn.close()
