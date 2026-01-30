import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print('=== RECEIPTS WITH 2025 DATES - OVERVIEW ===')
cur.execute("""
    SELECT 
        EXTRACT(MONTH FROM receipt_date) as month,
        COUNT(*) as count,
        SUM(gross_amount) as total,
        MIN(receipt_date) as earliest,
        MAX(receipt_date) as latest
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2025
    GROUP BY EXTRACT(MONTH FROM receipt_date)
    ORDER BY month
""")
print('Month | Count | Total Amount | Date Range')
print('-' * 70)
months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
for row in cur.fetchall():
    month_name = months[int(row[0])-1]
    total_str = f"${row[2]:,.2f}" if row[2] else "$0.00"
    print(f'{month_name:3} | {row[1]:5} | {total_str:15} | {row[3]} to {row[4]}')

print('\n=== SAMPLE 2025-02 RECEIPTS (First 30) ===')
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        category,
        created_from_banking,
        mapped_bank_account_id,
        description
    FROM receipts
    WHERE receipt_date >= '2025-02-01' AND receipt_date < '2025-03-01'
    ORDER BY receipt_date, receipt_id
    LIMIT 30
""")
print(f'{"ID":6} | {"Date":10} | {"Vendor":25} | {"Amount":10} | {"Category":15} | {"Bnk?":4} | {"Acct":4}')
print('-' * 100)
for row in cur.fetchall():
    rid, rdate, vendor, amount, category, from_banking, acct_id, desc = row
    banking = 'YES' if from_banking else 'NO'
    acct = str(acct_id) if acct_id else 'N/A'
    vendor_short = (vendor[:25] if vendor else 'Unknown')[:25]
    cat_short = (category[:15] if category else 'N/A')[:15]
    print(f'{rid:6} | {rdate} | {vendor_short:25} | ${amount:>9,.2f} | {cat_short:15} | {banking:4} | {acct:4}')
    if desc and len(desc) > 30:
        print(f'       Description: {desc[:80]}')

print('\n=== CHECKING BANKING_TRANSACTIONS FOR 2025-02 ===')
cur.execute("""
    SELECT 
        COUNT(*) as count,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE transaction_date >= '2025-02-01' AND transaction_date < '2025-03-01'
""")
row = cur.fetchone()
print(f'Banking transactions in Feb 2025: {row[0]}')
if row[0] > 0:
    print(f'  Date range: {row[1]} to {row[2]}')
    print(f'  Total debits: ${row[3]:,.2f}' if row[3] else '  Total debits: $0.00')
    print(f'  Total credits: ${row[4]:,.2f}' if row[4] else '  Total credits: $0.00')
else:
    print('  ⚠️  NO banking transactions found in Feb 2025!')
    print('  This suggests receipts have WRONG YEAR!')

print('\n=== CHECKING YEAR DISTRIBUTION IN RECEIPTS ===')
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year DESC
    LIMIT 20
""")
print('Year | Count  | Total Amount')
print('-' * 50)
for row in cur.fetchall():
    year = int(row[0])
    count = row[1]
    total = row[2] if row[2] else 0
    print(f'{year} | {count:6} | ${total:>15,.2f}')

# Check if these should be 2012 instead
print('\n=== CHECKING IF THESE MATCH 2012 BANKING PATTERN ===')
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE transaction_date >= '2012-02-01' AND transaction_date < '2012-03-01'
""")
count_2012 = cur.fetchone()[0]
print(f'Banking transactions in Feb 2012: {count_2012}')

# Check receipts with created_from_banking flag
print('\n=== RECEIPTS CREATED FROM BANKING IN 2025 ===')
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN created_from_banking THEN 1 ELSE 0 END) as from_banking,
        SUM(CASE WHEN mapped_bank_account_id = 1 THEN 1 ELSE 0 END) as cibc,
        SUM(CASE WHEN mapped_bank_account_id = 2 THEN 1 ELSE 0 END) as scotia
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2025
""")
row = cur.fetchone()
print(f'Total 2025 receipts: {row[0]}')
print(f'  Created from banking: {row[1]} ({row[1]/row[0]*100:.1f}%)')
print(f'  CIBC account (ID 1): {row[2]}')
print(f'  Scotia account (ID 2): {row[3]}')

cur.close()
conn.close()

print('\n' + '='*70)
print('⚠️  ANALYSIS COMPLETE')
print('='*70)
