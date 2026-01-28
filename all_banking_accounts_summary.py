import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("All Banking Accounts Summary by Year:\n")

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
    GROUP BY account_number, EXTRACT(YEAR FROM transaction_date)
    ORDER BY account_number, year
''')

rows = cur.fetchall()

# Group by account for better display
from collections import defaultdict
by_account = defaultdict(list)
for row in rows:
    by_account[row[0]].append(row)

for account in sorted(by_account.keys()):
    print(f"\n{account}")
    print("-" * 90)
    print(f"{'Year':<6} {'Count':<8} {'First Date':<12} {'Last Date':<12} {'Debits':<14} {'Credits':<14}")
    print("-" * 90)
    
    for year_data in by_account[account]:
        account_num, year, count, first_date, last_date, debits, credits = year_data
        print(f"{int(year):<6} {count:<8} {str(first_date):<12} {str(last_date):<12} ${float(debits):<13.2f} ${float(credits):<13.2f}")

cur.close()
conn.close()
