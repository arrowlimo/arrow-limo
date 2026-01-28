#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analyze 2014 CIBC statement data provided by user.
Extract key balances and transactions for reconciliation.
"""
import os
import psycopg2
from datetime import datetime

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

# Statement opening balance from header: $1,478.63 on Oct 24, 2014
# But transactions show Jan 02, 2014 starting with balance after first txn: $468.19

# Parse key month-end balances from the statement
statement_month_ends = {
    'Jan 31, 2014': 2167.87,  # After service charge
    'Feb 28, 2014': 442.45,   # After service charge
    'Mar 31, 2014': 1624.98,  # After service charge
    'Apr 30, 2014': 42.15,    # After service charge
    'May 30, 2014': 132.68,   # After service charge (before June txns)
    'Jun 25, 2014': 78.71,    # Last shown transaction
}

# Key fees from statement
service_charges = [
    ('2014-01-31', 10.00),
    ('2014-02-28', 7.00),
    ('2014-03-31', 7.00),
    ('2014-04-30', 8.00),
    ('2014-05-30', 6.00),
    # June service charge not shown yet in provided data
]

print("2014 CIBC Statement Analysis")
print("=" * 70)
print("\nAccount: 0228362 (Chequing 00339-02-28362)")
print("Statement period: Jan 01, 2014 to Oct 29, 2014")
print("Current balance (Oct 24): $1,478.63")

print("\nMonth-end balances from statement:")
for date, balance in statement_month_ends.items():
    print(f"  {date}: ${balance:,.2f}")

print("\nService charges:")
for date, amt in service_charges:
    print(f"  {date}: ${amt:.2f}")

# Check what's in database
conn = get_conn()
cur = conn.cursor()

print("\n" + "=" * 70)
print("Database comparison:")

cur.execute("""
    SELECT 
        COUNT(*) as txn_count,
        COALESCE(SUM(debit_amount), 0) as total_debits,
        COALESCE(SUM(credit_amount), 0) as total_credits,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        COUNT(CASE WHEN balance IS NULL THEN 1 END) as null_balances,
        COUNT(CASE WHEN balance = -1070963.39 THEN 1 END) as corrupted_balances
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2014
""")
row = cur.fetchone()
print(f"\nDatabase has {row[0]} transactions for 2014")
print(f"  Debits: ${row[1]:,.2f}")
print(f"  Credits: ${row[2]:,.2f}")
print(f"  Date range: {row[3]} to {row[4]}")
print(f"  NULL balances: {row[5]}")
print(f"  Corrupted balances (-1070963.39): {row[6]}")

# Check for service charge transactions
cur.execute("""
    SELECT transaction_date, description, debit_amount, balance
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2014
    AND description ILIKE '%service charge%'
    ORDER BY transaction_date
""")
db_service_charges = cur.fetchall()
print(f"\nService charges in database: {len(db_service_charges)}")
for row in db_service_charges:
    bal_str = f"${row[3]:,.2f}" if row[3] is not None else "NULL"
    print(f"  {row[0]}: {row[1]} ${row[2]:.2f} -> {bal_str}")

# Sample Jan transactions
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND transaction_date BETWEEN '2014-01-01' AND '2014-01-31'
    ORDER BY transaction_date
    LIMIT 10
""")
print("\nSample January transactions in database:")
for row in cur.fetchall():
    debit = f"${row[2]:,.2f}" if row[2] else ""
    credit = f"${row[3]:,.2f}" if row[3] else ""
    bal = f"${row[4]:,.2f}" if row[4] is not None else "NULL"
    print(f"  {row[0]} {row[1][:40]:40} D:{debit:10} C:{credit:10} Bal:{bal}")

cur.close()
conn.close()

print("\n" + "=" * 70)
print("Next steps:")
print("1. Import missing transactions from statement (if any)")
print("2. Update balance column for all 2014 transactions")
print("3. Verify month-end balances match statement")
