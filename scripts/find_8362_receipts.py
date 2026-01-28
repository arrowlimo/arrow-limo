#!/usr/bin/env python3
"""Find what makes up the 8,362 receipts the user wants to keep."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("=== SEARCHING FOR 8,362 RECEIPTS ===\n")

# Check various combinations
checks = [
    ("Receipts with NO banking link at all", 
     "SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NULL"),
    
    ("Receipts NOT created_from_banking", 
     "SELECT COUNT(*) FROM receipts WHERE created_from_banking IS NOT TRUE"),
    
    ("Receipts with NO banking AND NOT created_from_banking", 
     "SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NULL AND created_from_banking IS NOT TRUE"),
    
    ("Receipts from bank_id NULL (unmatched banking)", 
     """SELECT COUNT(DISTINCT r.receipt_id) FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.bank_id IS NULL"""),
    
    ("Receipts from account 8362", 
     """SELECT COUNT(DISTINCT r.receipt_id) FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '8362'"""),
    
    ("Receipts linked to non-verified banking", 
     """SELECT COUNT(DISTINCT r.receipt_id) FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.source_file NOT IN ('verified_2013_2014_scotia', 'CIBC_7461615_2012_2017_VERIFIED.xlsx')"""),
]

for name, query in checks:
    cur.execute(query)
    count = cur.fetchone()[0]
    match = "✅ MATCH!" if count == 8362 else ""
    print(f"{name:<60}: {count:>10,} {match}")

print("\n=== BREAKDOWN OF NON-VERIFIED RECEIPTS ===\n")

cur.execute("""
    SELECT 
        CASE 
            WHEN r.banking_transaction_id IS NULL THEN 'No banking link'
            WHEN bt.source_file IN ('verified_2013_2014_scotia', 'CIBC_7461615_2012_2017_VERIFIED.xlsx') THEN 'Verified banking'
            ELSE 'Non-verified banking'
        END as category,
        COUNT(*) as count
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    GROUP BY category
    ORDER BY count DESC
""")

for row in cur.fetchall():
    print(f"{row[0]:<30}: {row[1]:>10,}")

cur.close()
conn.close()
