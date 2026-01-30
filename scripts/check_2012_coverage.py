#!/usr/bin/env python
"""Check 2012 banking transaction coverage."""

import psycopg2
import os

# Database connection
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("\n" + "=" * 100)
print("2012 BANKING TRANSACTION COVERAGE")
print("=" * 100)

# Monthly breakdown by account
cur.execute("""
    SELECT 
        TO_CHAR(transaction_date, 'YYYY-MM') as month,
        account_number,
        COUNT(*) as txn_count,
        COALESCE(SUM(debit_amount), 0) as total_debits,
        COALESCE(SUM(credit_amount), 0) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY TO_CHAR(transaction_date, 'YYYY-MM'), account_number
    ORDER BY month, account_number
""")

print(f"\n{'Month':<10} {'Account':<15} {'Txns':<8} {'Debits':<18} {'Credits':<18}")
print("-" * 100)

rows = cur.fetchall()
for month, account, count, debits, credits in rows:
    print(f"{month:<10} {account:<15} {count:<8} ${debits:>15,.2f} ${credits:>15,.2f}")

# Overall summary
print("\n" + "=" * 100)
print("OVERALL 2012 SUMMARY")
print("=" * 100)

cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        COALESCE(SUM(debit_amount), 0) as total_debits,
        COALESCE(SUM(credit_amount), 0) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY account_number
    ORDER BY account_number
""")

print(f"\n{'Account':<15} {'Txns':<8} {'First Date':<12} {'Last Date':<12} {'Debits':<18} {'Credits':<18}")
print("-" * 100)

account_rows = cur.fetchall()
for account, count, first_date, last_date, debits, credits in account_rows:
    print(f"{account:<15} {count:<8} {str(first_date):<12} {str(last_date):<12} ${debits:>15,.2f} ${credits:>15,.2f}")

# Check for gaps in monthly coverage
print("\n" + "=" * 100)
print("MONTHLY COVERAGE ANALYSIS")
print("=" * 100)

all_months = ['2012-01', '2012-02', '2012-03', '2012-04', '2012-05', '2012-06',
              '2012-07', '2012-08', '2012-09', '2012-10', '2012-11', '2012-12']

for account in ['0228362', '903990106011']:
    print(f"\nAccount {account} (CIBC: 0228362, Scotia: 903990106011):")
    
    cur.execute("""
        SELECT TO_CHAR(transaction_date, 'YYYY-MM') as month, COUNT(*)
        FROM banking_transactions
        WHERE account_number = %s 
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY TO_CHAR(transaction_date, 'YYYY-MM')
        ORDER BY month
    """, (account,))
    
    months_with_data = {row[0]: row[1] for row in cur.fetchall()}
    
    for month in all_months:
        if month in months_with_data:
            print(f"  {month}: ✅ {months_with_data[month]} transactions")
        else:
            print(f"  {month}: ❌ NO DATA")

# Check for receipts coverage
print("\n" + "=" * 100)
print("2012 RECEIPTS COVERAGE")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as receipt_count,
        COALESCE(SUM(gross_amount), 0) as total_amount,
        MIN(receipt_date) as first_date,
        MAX(receipt_date) as last_date
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
""")

receipt_row = cur.fetchone()
print(f"\nBusiness Receipts: {receipt_row[0]} receipts")
print(f"Total Amount: ${receipt_row[1]:,.2f}")
print(f"Date Range: {receipt_row[2]} to {receipt_row[3]}")

# Check for charter/payment coverage
print("\n" + "=" * 100)
print("2012 CHARTERS & PAYMENTS COVERAGE")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as charter_count,
        COALESCE(SUM(total_amount_due), 0) as total_revenue,
        COALESCE(SUM(paid_amount), 0) as total_paid
    FROM charters
    WHERE EXTRACT(YEAR FROM charter_date) = 2012
""")

charter_row = cur.fetchone()
print(f"\nCharters: {charter_row[0]} trips")
print(f"Total Revenue: ${charter_row[1]:,.2f}")
print(f"Total Paid: ${charter_row[2]:,.2f}")

cur.execute("""
    SELECT 
        COUNT(*) as payment_count,
        COALESCE(SUM(amount), 0) as total_payments
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
""")

payment_row = cur.fetchone()
print(f"\nPayments: {payment_row[0]} transactions")
print(f"Total Amount: ${payment_row[1]:,.2f}")

cur.close()
conn.close()

print("\n" + "=" * 100)
