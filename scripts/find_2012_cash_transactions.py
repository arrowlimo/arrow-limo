#!/usr/bin/env python3
"""Find all cash transactions in 2012 - both expenses and income."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n" + "="*80)
print("2012 CASH TRANSACTIONS ANALYSIS")
print("="*80)

# Check receipts for cash expenses
print("\n1. CASH EXPENSES (Receipts):")
print("-"*80)

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (description ILIKE '%cash%' OR category = 'cash')
""")
result = cur.fetchone()
print(f"Total cash receipt transactions: {result[0]}")
print(f"Total cash expenses: ${result[1] or 0:.2f}")

# Get sample cash receipts
cur.execute("""
    SELECT receipt_date, vendor_name, description, gross_amount, category
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    AND (description ILIKE '%cash%' OR category = 'cash')
    ORDER BY receipt_date
    LIMIT 20
""")
cash_receipts = cur.fetchall()
if cash_receipts:
    print("\nSample cash receipts:")
    for date, vendor, desc, amt, cat in cash_receipts:
        print(f"  {date} ${amt:>8.2f} {vendor or 'Unknown':<30} {desc[:40]}")

# Check payments for cash income
print("\n\n2. CASH INCOME (Payments):")
print("-"*80)

cur.execute("""
    SELECT COUNT(*), SUM(amount)
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
    AND payment_method = 'cash'
""")
result = cur.fetchone()
print(f"Total cash payment transactions: {result[0]}")
print(f"Total cash income: ${result[1] or 0:.2f}")

# Get sample cash payments
cur.execute("""
    SELECT payment_date, reserve_number, amount, notes
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2012
    AND payment_method = 'cash'
    ORDER BY payment_date
    LIMIT 20
""")
cash_payments = cur.fetchall()
if cash_payments:
    print("\nSample cash payments:")
    for date, reserve, amt, notes in cash_payments:
        print(f"  {date} Reserve:{reserve or 'N/A':<10} ${amt:>8.2f} {notes or ''}")

# Check banking for cash transactions
print("\n\n3. CASH DEPOSITS/WITHDRAWALS (Banking):")
print("-"*80)

cur.execute("""
    SELECT COUNT(*), SUM(credit_amount), SUM(debit_amount)
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND description ILIKE '%cash%'
""")
result = cur.fetchone()
print(f"Total banking cash transactions: {result[0]}")
print(f"Total cash deposits: ${result[1] or 0:.2f}")
print(f"Total cash withdrawals: ${result[2] or 0:.2f}")

# Get sample banking cash transactions
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND description ILIKE '%cash%'
    ORDER BY transaction_date
    LIMIT 20
""")
cash_banking = cur.fetchall()
if cash_banking:
    print("\nSample banking cash transactions:")
    for date, desc, debit, credit in cash_banking:
        if debit:
            print(f"  {date} WITHDRAWAL ${debit:>8.2f} {desc[:50]}")
        else:
            print(f"  {date} DEPOSIT    ${credit:>8.2f} {desc[:50]}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("\nNote: Cash transactions may not appear in banking statements")
print("      as they are handled separately from bank deposits.")
print("\nCheck LMS Reserve table for payment type 'Cash' to find cash income.")

cur.close()
conn.close()

print("\n")
