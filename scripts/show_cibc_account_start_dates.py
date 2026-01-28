#!/usr/bin/env python3
"""Show earliest transaction date for each CIBC account."""
import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')
cur = conn.cursor()

print("=" * 100)
print("CIBC ACCOUNT START DATES")
print("=" * 100)
print()

# Get all CIBC accounts with their earliest dates
cur.execute("""
    SELECT 
        account_number,
        MIN(transaction_date) as earliest_date,
        MAX(transaction_date) as latest_date,
        COUNT(*) as total_transactions
    FROM banking_transactions
    WHERE account_number LIKE '%0228362%'
       OR account_number LIKE '%3648117%'
       OR account_number LIKE '%8314462%'
       OR account_number = '0228362'
       OR account_number = '3648117'
       OR account_number = '8314462'
    GROUP BY account_number
    ORDER BY account_number
""")

accounts = cur.fetchall()

print(f"{'Account Number':20} | {'Earliest Date':15} | {'Latest Date':15} | {'Total Txns':>12}")
print("-" * 100)

for acct, earliest, latest, count in accounts:
    print(f"{acct:20} | {str(earliest):15} | {str(latest):15} | {count:12,}")

print("\n" + "=" * 100)
print("ACCOUNT DETAILS")
print("=" * 100)
print()

account_names = {
    '0228362': 'CIBC Main Checking Account',
    '3648117': 'CIBC Business Deposit Account (alias 0534)',
    '8314462': 'CIBC Vehicle Loan Account'
}

for acct, earliest, latest, count in accounts:
    acct_clean = acct.strip()
    name = account_names.get(acct_clean, 'Unknown CIBC Account')
    
    print(f"📍 {name}")
    print(f"   Account: {acct}")
    print(f"   Start Date: {earliest} ({earliest.strftime('%B %Y')})")
    print(f"   Latest Date: {latest} ({latest.strftime('%B %Y')})")
    print(f"   Total Transactions: {count:,}")
    
    # Check for gaps
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date)::int as year,
            ARRAY_AGG(DISTINCT EXTRACT(MONTH FROM transaction_date)::int ORDER BY EXTRACT(MONTH FROM transaction_date)::int) as months
        FROM banking_transactions
        WHERE account_number = %s
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """, (acct,))
    
    years_data = cur.fetchall()
    print(f"   Coverage by Year:")
    for year, months in years_data:
        month_names = [['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1] for m in months]
        missing = [m for m in range(1, 13) if m not in months]
        if missing:
            missing_names = [['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1] for m in missing]
            print(f"      {year}: {len(months)}/12 months (missing: {', '.join(missing_names)})")
        else:
            print(f"      {year}: ✓ Complete (12/12 months)")
    
    print()

conn.close()
