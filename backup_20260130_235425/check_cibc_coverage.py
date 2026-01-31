#!/usr/bin/env python3
"""Check CIBC banking transaction coverage by year."""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

print("=" * 100)
print("CIBC BANKING TRANSACTION COVERAGE BY YEAR")
print("=" * 100)
print()

# Check what account identification columns exist
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    AND (column_name LIKE '%account%' OR column_name LIKE '%bank%')
    ORDER BY column_name
""")

print("Account identification columns in banking_transactions:")
for col in cur.fetchall():
    print(f"  - {col[0]}")
print()

# Get all distinct account values to identify CIBC
cur.execute("""
    SELECT DISTINCT account_number, COUNT(*) as tx_count
    FROM banking_transactions
    WHERE account_number IS NOT NULL
    GROUP BY account_number
    ORDER BY tx_count DESC
""")

print("Accounts in banking_transactions:")
for acct, count in cur.fetchall():
    marker = "← CIBC" if "0228362" in str(acct) else ""
    print(f"  {acct}: {count:,} transactions {marker}")

# Now analyze CIBC coverage
cibc_account = "0228362"

print("\n" + "=" * 100)
print(f"CIBC ACCOUNT {cibc_account} - MONTHLY COVERAGE")
print("=" * 100)
print()

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM transaction_date)::INT as year,
        EXTRACT(MONTH FROM transaction_date)::INT as month,
        COUNT(*) as tx_count,
        COUNT(DISTINCT EXTRACT(DAY FROM transaction_date)) as days_with_data,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest,
        SUM(CASE WHEN debit_amount IS NOT NULL AND debit_amount > 0 THEN 1 ELSE 0 END) as debits,
        SUM(CASE WHEN credit_amount IS NOT NULL AND credit_amount > 0 THEN 1 ELSE 0 END) as credits
    FROM banking_transactions
    WHERE account_number LIKE %s
    GROUP BY EXTRACT(YEAR FROM transaction_date), EXTRACT(MONTH FROM transaction_date)
    ORDER BY year, month
""", (f"%{cibc_account}%",))

monthly_data = cur.fetchall()

# Reorganize by year
years_dict = {}
for year, month, tx_count, days, earliest, latest, debits, credits in monthly_data:
    if year not in years_dict:
        years_dict[year] = []
    years_dict[year].append({
        'month': month,
        'tx_count': tx_count,
        'days': days,
        'earliest': earliest,
        'latest': latest,
        'debits': debits,
        'credits': credits
    })

# Analyze by year
print(f"{'Year':6} | {'Months':8} | {'Total TX':>10} | {'Days Covered':>12} | {'Debits':>8} | {'Credits':>8} | Status")
print("-" * 100)

for year in sorted(years_dict.keys()):
    months = years_dict[year]
    month_count = len(months)
    total_tx = sum(m['tx_count'] for m in months)
    total_days = sum(m['days'] for m in months)
    total_debits = sum(m['debits'] for m in months)
    total_credits = sum(m['credits'] for m in months)
    
    # Determine status
    if month_count == 12:
        status = "✓ COMPLETE (12 months)"
    elif month_count >= 10:
        status = f"⚠ PARTIAL ({month_count} months)"
    else:
        status = f"❌ SPARSE ({month_count} months)"
    
    print(f"{int(year):6} | {month_count:8} | {total_tx:10,} | {total_days:12,} | {total_debits:8,} | {total_credits:8,} | {status}")

# Detailed missing months
print("\n" + "=" * 100)
print("DETAILED YEAR-BY-YEAR BREAKDOWN")
print("=" * 100)

month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

for year in sorted(years_dict.keys()):
    months = years_dict[year]
    months_present = set(m['month'] for m in months)
    months_missing = set(range(1, 13)) - months_present
    
    print(f"\n{int(year)}:")
    
    # Show coverage
    coverage_pct = (len(months_present) / 12) * 100
    print(f"  Coverage: {coverage_pct:.1f}% ({len(months_present)}/12 months)")
    
    if months_missing:
        missing_names = [month_names[m-1] for m in sorted(months_missing)]
        print(f"  Missing: {', '.join(missing_names)}")
    else:
        print(f"  ✓ All months present")
    
    # Transaction summary
    total_tx = sum(m['tx_count'] for m in months)
    avg_tx_per_month = total_tx / len(months) if months else 0
    print(f"  Transactions: {total_tx:,} total ({avg_tx_per_month:.0f} avg/month)")

# Summary
print("\n" + "=" * 100)
print("SUMMARY - YEARS NEEDING FULL CIBC DOWNLOADS")
print("=" * 100)

complete_years = [y for y in sorted(years_dict.keys()) if len(years_dict[y]) == 12]
incomplete_years = [y for y in sorted(years_dict.keys()) if len(years_dict[y]) < 12]

print(f"\n✓ COMPLETE YEARS (12/12 months): {', '.join(str(int(y)) for y in complete_years) if complete_years else 'None'}")
if incomplete_years:
    print(f"❌ INCOMPLETE YEARS: {', '.join(str(int(y)) for y in incomplete_years)}")
    print(f"\n   Years needing FULL bank downloads from CIBC: {', '.join(str(int(y)) for y in incomplete_years)}")
else:
    print(f"✓ All years have complete monthly coverage!")

conn.close()
