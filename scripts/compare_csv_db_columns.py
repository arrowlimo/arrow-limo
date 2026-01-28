import csv
import psycopg2
from datetime import datetime

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Parse just first 10 CSV transactions
csv_txns = []
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        if i >= 10:
            break
        if len(row) >= 3:
            date_str = row[0]
            desc = row[1]
            debit = row[2].strip() if row[2].strip() else None
            credit = row[3].strip() if row[3].strip() else None
            
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                debit_amt = float(debit) if debit else None
                credit_amt = float(credit) if credit else None
                
                csv_txns.append({
                    'date': date,
                    'desc': desc,
                    'debit': debit_amt,
                    'credit': credit_amt,
                    'amount': debit_amt if debit_amt else credit_amt
                })
            except ValueError:
                pass

print("SAMPLE CSV TRANSACTIONS:")
print(f"{'Date':<12} {'Description':<60} {'Amount':>10}")
print("-" * 85)
for t in csv_txns:
    amt = t['amount']
    print(f"{t['date']} | {t['desc'][:58]:<58} | ${amt:>9.2f}")

print()
print("=" * 85)
print()

# Get same dates from DB
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

dates_to_check = [t['date'] for t in csv_txns]
dates_str = ','.join([f"'{d}'" for d in dates_to_check])

cur.execute(f"""
    SELECT 
        transaction_date,
        description,
        vendor_extracted,
        debit_amount,
        credit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
        AND transaction_date IN ({dates_str})
    ORDER BY transaction_date DESC
""")

print("SAMPLE DATABASE TRANSACTIONS (same dates):")
print(f"{'Date':<12} {'Description':<35} {'Vendor':<25} {'Amount':>10}")
print("-" * 85)
for date, desc, vendor, debit, credit in cur.fetchall():
    amt = debit if debit else credit
    print(f"{date} | {desc[:33]:<33} | {str(vendor)[:23]:<23} | ${amt:>9.2f}")

cur.close()
conn.close()
