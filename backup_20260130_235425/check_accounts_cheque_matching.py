#!/usr/bin/env python3
"""Check other bank accounts for possible cheque matching opportunities."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("CHECK OTHER BANK ACCOUNTS FOR CHEQUE MATCHING")
print("=" * 100 + "\n")

# List all bank accounts
print("Available bank accounts:\n")

cur.execute("""
    SELECT DISTINCT account_number FROM banking_transactions
    ORDER BY account_number
""")

accounts = cur.fetchall()
for (acct,) in accounts:
    cur.execute("""
        SELECT COUNT(*) as tx_count,
               MIN(transaction_date) as earliest,
               MAX(transaction_date) as latest,
               SUM(COALESCE(debit_amount, 0) + COALESCE(credit_amount, 0)) as volume
        FROM banking_transactions
        WHERE account_number = %s
    """, (acct,))
    
    count, earliest, latest, volume = cur.fetchone()
    print(f"Account {acct}:")
    print(f"  Transactions: {count}")
    print(f"  Period: {earliest.year if earliest else 'N/A'} - {latest.year if latest else 'N/A'}")
    print(f"  Volume: ${float(volume):,.2f}")
    print()

# Check cheque_register for all accounts
print("=" * 100)
print("CHEQUE_REGISTER STATUS BY ACCOUNT")
print("=" * 100 + "\n")

cur.execute("""
    SELECT account_number, status, COUNT(*) as count, SUM(amount) as total
    FROM cheque_register
    GROUP BY account_number, status
    ORDER BY account_number, status
""")

print("Cheque Register by Account:\n")
current_acct = None
for acct, status, count, total in cur.fetchall():
    if acct != current_acct:
        print(f"\nAccount {acct}:")
        current_acct = acct
    print(f"  {status:15} | {count:4d} cheques | ${float(total):12,.2f}")

# Check unmatched cheques for other accounts
print("\n" + "=" * 100)
print("UNMATCHED CHEQUES BY ACCOUNT")
print("=" * 100 + "\n")

cur.execute("""
    SELECT account_number, COUNT(*) as unmatched_count, SUM(amount) as total
    FROM cheque_register
    WHERE status = 'unmatched'
    GROUP BY account_number
    ORDER BY account_number
""")

results = cur.fetchall()
if results:
    for acct, count, total in results:
        print(f"Account {acct}: {count} unmatched cheques, ${float(total):,.2f}")
else:
    print("No unmatched cheques found in other accounts\n")

# Detailed unmatched cheques from 2012 CIBC (our account)
print("\n" + "=" * 100)
print("UNMATCHED 2012 CIBC CHEQUES (0228362) - DETAILS")
print("=" * 100 + "\n")

cur.execute("""
    SELECT cheque_number, cheque_date, payee, amount, memo
    FROM cheque_register
    WHERE account_number = '0228362'
    AND status = 'unmatched'
    ORDER BY cheque_date
    LIMIT 20
""")

print("Sample of unmatched cheques:\n")
for cheque_num, cheque_date, payee, amount, memo in cur.fetchall():
    print(f"Cheque #{cheque_num} | {cheque_date} | ${amount:8,.2f} | {payee}")
    if memo:
        print(f"  Memo: {memo}")

cur.execute("""
    SELECT COUNT(*) FROM cheque_register
    WHERE account_number = '0228362'
    AND status = 'unmatched'
""")
total_unmatched = cur.fetchone()[0]
print(f"\n... and {total_unmatched - 20} more unmatched cheques" if total_unmatched > 20 else "")

cur.close()
conn.close()

print("\n✅ Analysis complete")
