import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("E-TRANSFER DATE RANGES")
print("="*80)

# Banking date range
cur.execute("""
    SELECT MIN(transaction_date), MAX(transaction_date), COUNT(*)
    FROM banking_transactions
    WHERE description ILIKE '%E-TRANSFER%' OR description ILIKE '%EMAIL TRANSFER%'
""")
min_date, max_date, count = cur.fetchone()
print(f"\nBANKING TRANSACTIONS:")
print(f"  Date range: {min_date} to {max_date}")
print(f"  Total: {count:,} transactions")

# Check Outlook email date
import csv
with open('l:/limo/reports/etransfer_emails.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    dates = []
    for row in reader:
        from datetime import datetime
        email_date = datetime.fromisoformat(row['email_date'].replace('T', ' '))
        dates.append(email_date)
    
    if dates:
        min_email = min(dates)
        max_email = max(dates)
        print(f"\nOUTLOOK EMAILS:")
        print(f"  Date range: {min_email.date()} to {max_email.date()}")
        print(f"  Total: {len(dates):,} emails")
        
        print(f"\n⚠️  PROBLEM: Outlook emails are only from October 2024!")
        print(f"   Banking has e-transfers from {min_date} to {max_date}")
        print(f"   Need to scan older emails from 2012-2014 period")

cur.close()
conn.close()
