#!/usr/bin/env python3
"""Check which banking accounts are in the database for 2012"""
import psycopg2
import os

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

conn = psycopg2.connect(**DSN)
cur = conn.cursor()

print("=" * 80)
print("2012 BANKING ACCOUNTS ANALYSIS")
print("=" * 80)
print()

# Get account breakdown
cur.execute("""
    SELECT 
        COALESCE(account_number, 'NULL') as account,
        COUNT(*) as tx_count,
        COALESCE(SUM(debit_amount), 0) as total_debits,
        COALESCE(SUM(credit_amount), 0) as total_credits,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY account_number
    ORDER BY account_number
""")

rows = cur.fetchall()

print(f"Found {len(rows)} distinct account(s):\n")

for row in rows:
    account, count, debits, credits, first_date, last_date = row
    print(f"Account: {account}")
    print(f"  Transactions: {count:,}")
    print(f"  Debits:       ${float(debits):,.2f}")
    print(f"  Credits:      ${float(credits):,.2f}")
    print(f"  Net:          ${float(credits) - float(debits):,.2f}")
    print(f"  Date Range:   {first_date} to {last_date}")
    print()

# Check if there are specific categories
cur.execute("""
    SELECT 
        COALESCE(category, 'UNCATEGORIZED') as cat,
        COUNT(*) as tx_count,
        COALESCE(SUM(debit_amount), 0) as total_debits,
        COALESCE(SUM(credit_amount), 0) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY category
    ORDER BY tx_count DESC
    LIMIT 10
""")

rows = cur.fetchall()

print("=" * 80)
print("TOP 10 CATEGORIES:")
print("=" * 80)
print()

for row in rows:
    cat, count, debits, credits = row
    print(f"{cat}: {count:,} transactions, Debits: ${float(debits):,.2f}, Credits: ${float(credits):,.2f}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("NOTE: QuickBooks shows account '1000 - CIBC Bank' with $833,621 in deposits")
print("      Database account 0228362 shows only $319,689 in credits")
print("      This suggests database may be missing ~$513K in deposit transactions")
print("=" * 80)
