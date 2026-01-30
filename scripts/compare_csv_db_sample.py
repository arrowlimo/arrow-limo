import csv
import psycopg2
from datetime import datetime

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Read CSV
csv_txns = {}
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 3:
            date_str = row[0]
            desc = row[1]
            debit = row[2].strip() if row[2].strip() else None
            credit = row[3].strip() if row[3].strip() else None
            
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                debit_amt = float(debit) if debit else None
                credit_amt = float(credit) if credit else None
                amount = debit_amt if debit_amt else credit_amt
                
                key = f"{date}|{amount}"
                csv_txns[key] = {'date': date, 'desc': desc, 'amount': amount}
            except ValueError:
                pass

# Get from DB
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT 
        transaction_date,
        COALESCE(vendor_extracted, description),
        CASE 
            WHEN debit_amount IS NOT NULL AND debit_amount > 0 THEN -debit_amount
            WHEN credit_amount IS NOT NULL AND credit_amount > 0 THEN credit_amount
            ELSE 0
        END as amount
    FROM banking_transactions
    WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2018
    ORDER BY transaction_date DESC
    LIMIT 30
""")

print("SAMPLE DATABASE TRANSACTIONS (last 30):")
print(f"{'Date':<12} {'Amount':>12} {'Description':<60}")
print("-" * 85)
for date, desc, amt in cur.fetchall():
    print(f"{date} | {amt:>11.2f} | {desc[:58]}")

cur.close()
conn.close()
