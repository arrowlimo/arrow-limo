#!/usr/bin/env python3
"""Analyze banking data to understand verification patterns."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=== BANKING ACCOUNT NUMBERS BY BANK_ID ===\n")
cur.execute("""
    SELECT bank_id, account_number, COUNT(*) as count
    FROM banking_transactions
    WHERE account_number IS NOT NULL
    GROUP BY bank_id, account_number
    ORDER BY bank_id, count DESC
""")
for row in cur.fetchall():
    acct = row[1] if row[1] else "NULL"
    print(f"  bank_id {row[0]}: {acct} ({row[2]:,} transactions)")

print("\n\n=== SOURCE FILES MENTIONING PDF (likely verified) ===\n")
cur.execute("""
    SELECT DISTINCT source_file, COUNT(*) as count
    FROM banking_transactions
    WHERE source_file ILIKE '%pdf%' OR source_file ILIKE '%verified%'
    GROUP BY source_file
    ORDER BY count DESC
    LIMIT 20
""")
result = cur.fetchall()
if result:
    for row in result:
        print(f"  {row[0]:<60} ({row[1]:,} trans)")
else:
    print("  No files with 'pdf' or 'verified' in name found")

print("\n\n=== RECEIPTS BY SOURCE ===\n")
cur.execute("""
    SELECT 
        CASE 
            WHEN created_from_banking THEN 'Created from banking'
            WHEN banking_transaction_id IS NOT NULL THEN 'Linked to banking'
            ELSE 'No banking link'
        END as source_type,
        COUNT(*) as count
    FROM receipts
    GROUP BY source_type
    ORDER BY count DESC
""")
for row in cur.fetchall():
    print(f"  {row[0]:<25}: {row[1]:,}")

print("\n\n=== RECEIPTS WITH created_from_banking BY BANK ===\n")
cur.execute("""
    SELECT 
        bt.bank_id,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC'
            WHEN bt.bank_id = 2 THEN 'Scotia'
            ELSE 'Other'
        END as bank_name,
        COUNT(*) as receipt_count
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.created_from_banking = true
    GROUP BY bt.bank_id
    ORDER BY bt.bank_id
""")
for row in cur.fetchall():
    bank_id, bank_name, count = row
    print(f"  bank_id {bank_id} ({bank_name}): {count:,} receipts")

cur.close()
conn.close()
