#!/usr/bin/env python3
"""Check 2025 banking transaction coverage"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("\n" + "="*80)
print("2025 BANKING TRANSACTION COVERAGE")
print("="*80)

# Check banking transactions by account for 2025
cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as transactions,
        MIN(transaction_date) as earliest,
        MAX(transaction_date) as latest,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    GROUP BY account_number
    ORDER BY transactions DESC
""")

print(f"\n📊 2025 Banking Transactions by Account:")
print(f"{'Account':<15} {'Count':<10} {'Earliest':<12} {'Latest':<12} {'Debits':<15} {'Credits':<15}")
print("-" * 95)

total_txs = 0
for acct, count, earliest, latest, debits, credits in cur.fetchall():
    total_txs += count
    acct_name = acct or 'NULL'
    print(f"{acct_name:<15} {count:<10,} {str(earliest):<12} {str(latest):<12} ${debits or 0:<14,.2f} ${credits or 0:<14,.2f}")

print(f"\nTotal 2025 transactions: {total_txs:,}")

# Check coverage by month
cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        account_number,
        COUNT(*) as count
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM'), account_number
    ORDER BY month, account_number
""")

print(f"\n📅 2025 Monthly Coverage:")
print(f"{'Month':<10} {'Account':<15} {'Transactions'}")
print("-" * 45)

current_month = None
for month, acct, count in cur.fetchall():
    if month != current_month:
        if current_month is not None:
            print("-" * 45)
        current_month = month
    acct_name = acct or 'NULL'
    print(f"{month:<10} {acct_name:<15} {count:>12,}")

# Check for missing months
cur.execute("""
    SELECT DISTINCT TO_CHAR(transaction_date, 'YYYY-MM') as month
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2025
    ORDER BY month
""")

months_present = [row[0] for row in cur.fetchall()]
all_2025_months = [f"2025-{m:02d}" for m in range(1, 13)]
missing_months = [m for m in all_2025_months if m not in months_present]

if missing_months:
    print(f"\n⚠️  Missing Months: {', '.join(missing_months)}")
else:
    print(f"\n✅ All 2025 months have banking data")

# Check latest transaction date
cur.execute("""
    SELECT 
        account_number,
        MAX(transaction_date) as latest_tx
    FROM banking_transactions
    GROUP BY account_number
    ORDER BY latest_tx DESC
""")

print(f"\n📆 Latest Banking Transaction by Account:")
print(f"{'Account':<15} {'Latest Transaction'}")
print("-" * 40)
for acct, latest in cur.fetchall():
    acct_name = acct or 'NULL'
    print(f"{acct_name:<15} {latest}")

# Check account configurations
cur.execute("""
    SELECT 
        account_id,
        account_number,
        account_name,
        bank_name,
        is_active
    FROM bank_accounts
    ORDER BY account_id
""")

print(f"\n🏦 Bank Account Configurations:")
print(f"{'ID':<5} {'Account Number':<15} {'Name':<30} {'Bank':<15} {'Active'}")
print("-" * 85)
for acc_id, acc_num, acc_name, bank, active in cur.fetchall():
    status = "✅" if active else "❌"
    print(f"{acc_id:<5} {acc_num or 'NULL':<15} {acc_name or 'NULL':<30} {bank or 'NULL':<15} {status}")

print(f"\n" + "="*80)
print("NEXT STEPS TO DOWNLOAD 2025 BANKING DATA")
print("="*80)
print(f"""
1. CIBC Account 0228362 (Primary)
   - Log into CIBC online banking
   - Download transactions: Jan 1, 2025 → Dec 22, 2025
   - Format: CSV or QFX
   - Save to: L:\\limo\\data\\banking\\cibc_2025_*.csv

2. Scotia Account 903990106011 (Secondary)
   - Log into Scotia online banking
   - Download transactions: Jan 1, 2025 → Dec 22, 2025
   - Format: CSV
   - Save to: L:\\limo\\data\\banking\\scotia_2025_*.csv

3. Square Payouts
   - Already synced via API ({total_txs:,} transactions)
   - Or download from Square dashboard as backup

4. After downloading, run import scripts:
   python scripts/import_cibc_banking.py --file L:\\limo\\data\\banking\\cibc_2025_*.csv
   python scripts/import_scotia_banking.py --file L:\\limo\\data\\banking\\scotia_2025_*.csv
""")

cur.close()
conn.close()

print("="*80)
