import csv
import psycopg2
from datetime import datetime
from collections import Counter

csv_file = r"L:\limo\CIBC UPLOADS\0228362 (CIBC checking account)\cibc 8362 2018.csv"

# Count transactions by date in CSV
csv_by_date = Counter()
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 1:
            try:
                date = datetime.strptime(row[0], '%Y-%m-%d').date()
                csv_by_date[date] += 1
            except ValueError:
                pass

# Count transactions by date in DB
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT transaction_date, COUNT(*) 
    FROM banking_transactions
    WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2018
    GROUP BY transaction_date
    ORDER BY transaction_date DESC
""")

db_by_date = {row[0]: row[1] for row in cur.fetchall()}
cur.close()
conn.close()

# Find mismatches
print("DATES WITH DIFFERENT TRANSACTION COUNTS (CSV vs DB):")
print(f"{'Date':<12} {'CSV':<6} {'DB':<6} {'Diff':<6} {'Status'}")
print("-" * 50)

for date in sorted(set(csv_by_date.keys()) | set(db_by_date.keys()), reverse=True):
    csv_count = csv_by_date.get(date, 0)
    db_count = db_by_date.get(date, 0)
    if csv_count != db_count:
        diff = csv_count - db_count
        status = f"CSV has {diff} extra" if diff > 0 else f"DB has {abs(diff)} extra"
        print(f"{date} | {csv_count:<5} | {db_count:<5} | {diff:<5} | {status}")

print()
print(f"TOTALS:")
print(f"  CSV: {sum(csv_by_date.values())} transactions")
print(f"  DB:  {sum(db_by_date.values())} transactions")
print(f"  Difference: {sum(csv_by_date.values()) - sum(db_by_date.values())} (CSV has more)")
