import psycopg2
import csv
from datetime import datetime

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get all Scotia Bank 2012 transactions
cur.execute('''
    SELECT 
        transaction_id,
        transaction_date,
        account_number,
        description,
        debit_amount,
        credit_amount,
        created_at
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date, transaction_id
''')

rows = cur.fetchall()
print(f'Retrieved {len(rows)} Scotia Bank 2012 transactions')

# Write to CSV (Excel-compatible)
with open('reports/Scotia_Bank_2012_Full_Report.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    
    # Header
    # Header
    writer.writerow([
        'Transaction ID',
        'Date',
        'Account Number',
        'Description',
        'Debit Amount',
        'Credit Amount',
        'Running Balance',
        'Created At'
    ])
    
    # Calculate running balance
    running_balance = 0
    for row in rows:
        tid, date, acct, desc, debit, credit, created = row
        # Update running balance
        if debit:
            running_balance -= float(debit)
        if credit:
            running_balance += float(credit)
        
        writer.writerow([
            tid,
            date.strftime('%Y-%m-%d'),
            acct,
            desc,
            f'{float(debit):.2f}' if debit else '0.00',
            f'{float(credit):.2f}' if credit else '0.00',
            f'{running_balance:.2f}',
            created.strftime('%Y-%m-%d %H:%M:%S') if created else ''
        ])

# Generate summary stats
cur.execute('''
    SELECT 
        EXTRACT(MONTH FROM transaction_date) as month,
        COUNT(*) as transaction_count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits,
        SUM(credit_amount) - SUM(debit_amount) as net_flow
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY EXTRACT(MONTH FROM transaction_date)
    ORDER BY month
''')

summary = cur.fetchall()

# Write summary sheet
with open('reports/Scotia_Bank_2012_Monthly_Summary.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['Month', 'Transaction Count', 'Total Debits', 'Total Credits', 'Net Cash Flow'])
    
    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June', 
                   'July', 'August', 'September', 'October', 'November', 'December']
    
    total_txns = 0
    total_debits = 0
    total_credits = 0
    
    for month, count, debits, credits, net in summary:
        total_txns += count
        total_debits += float(debits or 0)
        total_credits += float(credits or 0)
        
        writer.writerow([
            month_names[int(month)],
            count,
            f'{float(debits or 0):.2f}',
            f'{float(credits or 0):.2f}',
            f'{float(net or 0):.2f}'
        ])
    
    writer.writerow([])
    writer.writerow(['TOTAL', total_txns, f'{total_debits:.2f}', f'{total_credits:.2f}', f'{total_credits - total_debits:.2f}'])

cur.close()
conn.close()

print(f'[OK] Created Scotia_Bank_2012_Full_Report.csv ({len(rows)} transactions)')
print(f'[OK] Created Scotia_Bank_2012_Monthly_Summary.csv (12 months)')
print('')
print(f'Total Debits: ${total_debits:,.2f}')
print(f'Total Credits: ${total_credits:,.2f}')
print(f'Net Cash Flow: ${total_credits - total_debits:,.2f}')
