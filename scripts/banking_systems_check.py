#!/usr/bin/env python
"""Show CIBC and SCOTIABANK banking data."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "="*120)
print("BANKING SYSTEMS - CIBC and SCOTIABANK")
print("="*120)

# Check bank_id values
cur.execute("""
    SELECT DISTINCT bank_id, COUNT(*) as txn_count,
           MIN(transaction_date) as earliest_date,
           MAX(transaction_date) as latest_date,
           source_file
    FROM banking_transactions
    GROUP BY bank_id, source_file
    ORDER BY bank_id, source_file
""")

print("\nBanking data by bank_id and source_file:\n")
rows = cur.fetchall()
for bank_id, txn_count, earliest, latest, source_file in rows:
    print(f"  Bank ID: {bank_id}")
    print(f"    Transactions: {txn_count}")
    print(f"    Date Range: {earliest} to {latest}")
    print(f"    Source File: {source_file}")
    print()

# Check if there are CIBC or SCOTIABANK references in description or account
print("="*120)
print("CHECKING FOR 'CIBC' IN BANKING DATA")
print("="*120)
cur.execute("""
    SELECT DISTINCT bank_id, COUNT(*) as txn_count,
           MIN(transaction_date) as earliest_date,
           MAX(transaction_date) as latest_date
    FROM banking_transactions
    WHERE UPPER(description) LIKE '%CIBC%' OR account_number LIKE '%CIBC%'
    GROUP BY bank_id
    ORDER BY bank_id
""")
rows = cur.fetchall()
if rows:
    for bank_id, txn_count, earliest, latest in rows:
        print(f"  Bank ID: {bank_id} - {txn_count} transactions")
        print(f"    Date Range: {earliest} to {latest}")
        print()
else:
    print("  No CIBC references found in banking_transactions\n")

print("="*120)
print("CHECKING FOR 'SCOTIA' IN BANKING DATA")
print("="*120)
cur.execute("""
    SELECT DISTINCT bank_id, COUNT(*) as txn_count,
           MIN(transaction_date) as earliest_date,
           MAX(transaction_date) as latest_date
    FROM banking_transactions
    WHERE UPPER(description) LIKE '%SCOTIA%' OR account_number LIKE '%SCOTIA%'
    GROUP BY bank_id
    ORDER BY bank_id
""")
rows = cur.fetchall()
if rows:
    for bank_id, txn_count, earliest, latest in rows:
        print(f"  Bank ID: {bank_id} - {txn_count} transactions")
        print(f"    Date Range: {earliest} to {latest}")
        print()
else:
    print("  No SCOTIA references found in banking_transactions\n")

# Check mapped_bank_account table
print("="*120)
print("MAPPED BANK ACCOUNTS")
print("="*120)
cur.execute("""
    SELECT * FROM mapped_bank_account
    ORDER BY mapped_bank_account_id
""")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"  ID: {row[0]}")
        print(f"    Bank Name: {row[1] if row[1] else 'N/A'}")
        print(f"    Account: {row[2] if row[2] else 'N/A'}")
        print(f"    Description: {row[3] if row[3] else 'N/A'}")
        print()
else:
    print("  No mapped bank accounts found\n")

cur.close()
conn.close()
