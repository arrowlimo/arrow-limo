import csv
import psycopg2
from datetime import datetime

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Parse CSV
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
                
                # Create key: date | amount | description
                amt_str = f"{debit_amt:.2f}" if debit_amt else f"{credit_amt:.2f}"
                key = f"{date}|{amt_str}|{desc}"
                csv_txns[key] = {
                    'date': date, 
                    'desc': desc, 
                    'amount': debit_amt if debit_amt else credit_amt,
                    'is_debit': bool(debit_amt)
                }
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
            WHEN debit_amount IS NOT NULL AND debit_amount > 0 THEN debit_amount
            WHEN credit_amount IS NOT NULL AND credit_amount > 0 THEN credit_amount
            ELSE 0
        END as amount
    FROM banking_transactions
    WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2018
    ORDER BY transaction_date DESC
""")

db_txns = {}
for date, desc, amt in cur.fetchall():
    amt_str = f"{abs(amt):.2f}"
    key = f"{date}|{amt_str}|{desc}"
    db_txns[key] = {'date': date, 'desc': desc, 'amount': amt}

cur.close()
conn.close()

# Find missing in DB (in CSV but not in DB)
missing = []
for key in csv_txns:
    if key not in db_txns:
        missing.append(csv_txns[key])

print("TRANSACTIONS IN CSV BUT NOT IN DATABASE (14 missing):")
print(f"{'Date':<12} {'Type':<8} {'Amount':>12} {'Description':<55}")
print("-" * 90)

missing_sorted = sorted(missing, key=lambda x: x['date'], reverse=True)
for txn in missing_sorted:
    txn_type = "DEBIT" if txn['is_debit'] else "CREDIT"
    print(f"{txn['date']} | {txn_type:<7} | ${txn['amount']:>11.2f} | {txn['desc'][:53]}")

# Find extra in DB (in DB but not in CSV)
extra = []
for key in db_txns:
    if key not in csv_txns:
        extra.append(db_txns[key])

print()
print("TRANSACTIONS IN DATABASE BUT NOT IN CSV (2 extra):")
print(f"{'Date':<12} {'Amount':>12} {'Description':<55}")
print("-" * 80)

extra_sorted = sorted(extra, key=lambda x: x['date'], reverse=True)
for txn in extra_sorted:
    print(f"{txn['date']} | ${txn['amount']:>11.2f} | {txn['desc'][:53]}")
