#!/usr/bin/env python3
"""
Check if QuickBooks entries have receipt data.
Look for specific examples: Oct 1 2012 $10 car wash, Running on Empty $50
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("CHECKING QUICKBOOKS ENTRIES FOR RECEIPT DATA")
print("=" * 80)

# Search for Oct 1 2012 $10 car wash
print("\n1. SEARCHING: Oct 1 2012, $10 car wash")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, 
           description, reconciliation_status
    FROM banking_transactions
    WHERE transaction_date = '2012-10-01'
      AND (debit_amount = 10.00 OR credit_amount = 10.00)
      AND description ILIKE %s
    ORDER BY transaction_id
""", ('%car%wash%',))

results = cur.fetchall()
if results:
    print(f"Found {len(results)} transaction(s):")
    for tx_id, date, debit, credit, desc, status in results:
        amount = debit if debit else credit
        tx_type = 'DEBIT' if debit else 'CREDIT'
        print(f"\n  TX {tx_id} | {date} | ${amount:.2f} {tx_type}")
        print(f"  Description: {desc}")
        print(f"  Status: {status or 'ACTIVE'}")
        
        # Check for receipt
        cur.execute("""
            SELECT receipt_id, vendor_name, gross_amount, category
            FROM receipts
            WHERE banking_transaction_id = %s
        """, (tx_id,))
        
        receipt = cur.fetchone()
        if receipt:
            r_id, vendor, amount, category = receipt
            print(f"  ✅ HAS RECEIPT {r_id}: {vendor} | ${amount:.2f} | {category or 'No category'}")
        else:
            print(f"  ❌ NO RECEIPT")
else:
    print("❌ Not found - trying broader search...")
    
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount, 
               description
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-10-01' AND '2012-10-03'
          AND (debit_amount BETWEEN 9 AND 11 OR credit_amount BETWEEN 9 AND 11)
        ORDER BY transaction_date, transaction_id
        LIMIT 10
    """)
    
    results = cur.fetchall()
    if results:
        print(f"Similar transactions around Oct 1 2012 ($9-$11):")
        for tx_id, date, debit, credit, desc in results:
            amount = debit if debit else credit
            print(f"  TX {tx_id} | {date} | ${amount:.2f} | {desc[:60]}")

# Search for "Running on Empty" $50
print("\n\n2. SEARCHING: Running on Empty, $50")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, 
           description, reconciliation_status
    FROM banking_transactions
    WHERE description ILIKE %s
      AND (debit_amount = 50.00 OR credit_amount = 50.00)
    ORDER BY transaction_date
""", ('%running%empty%',))

results = cur.fetchall()
if results:
    print(f"Found {len(results)} transaction(s):")
    for tx_id, date, debit, credit, desc, status in results:
        amount = debit if debit else credit
        tx_type = 'DEBIT' if debit else 'CREDIT'
        print(f"\n  TX {tx_id} | {date} | ${amount:.2f} {tx_type}")
        print(f"  Description: {desc}")
        print(f"  Status: {status or 'ACTIVE'}")
        
        # Check for receipt
        cur.execute("""
            SELECT receipt_id, vendor_name, gross_amount, category
            FROM receipts
            WHERE banking_transaction_id = %s
        """, (tx_id,))
        
        receipt = cur.fetchone()
        if receipt:
            r_id, vendor, amount, category = receipt
            print(f"  ✅ HAS RECEIPT {r_id}: {vendor} | ${amount:.2f} | {category or 'No category'}")
        else:
            print(f"  ❌ NO RECEIPT")
else:
    print("❌ Not found - searching just 'running' or 'empty'...")
    
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount, description
        FROM banking_transactions
        WHERE (description ILIKE %s OR description ILIKE %s)
          AND transaction_date >= '2012-01-01' AND transaction_date <= '2012-12-31'
        ORDER BY transaction_date
        LIMIT 10
    """, ('%running%', '%empty%'))
    
    results = cur.fetchall()
    if results:
        print(f"Similar transactions in 2012:")
        for tx_id, date, debit, credit, desc in results:
            amount = debit if debit else credit
            print(f"  TX {tx_id} | {date} | ${amount:.2f} | {desc[:60]}")
    else:
        print("  None found")

# General QuickBooks entries with receipts
print("\n\n3. ALL 2012 BANKING ENTRIES WITH/WITHOUT RECEIPTS")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-12-31'
""")
total_2012 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.transaction_date >= '2012-01-01' AND bt.transaction_date <= '2012-12-31'
""")
with_receipts = cur.fetchone()[0]

print(f"Total banking entries in 2012: {total_2012:,}")
print(f"With receipts: {with_receipts:,}")
print(f"Without receipts: {total_2012 - with_receipts:,}")

if with_receipts > 0:
    print(f"\nSample 2012 entries WITH receipts:")
    cur.execute("""
        SELECT bt.transaction_id, bt.transaction_date, bt.debit_amount, bt.description,
               r.receipt_id, r.vendor_name, r.category
        FROM banking_transactions bt
        JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.transaction_date >= '2012-01-01' AND bt.transaction_date <= '2012-12-31'
        ORDER BY bt.transaction_date
        LIMIT 10
    """)
    
    for tx_id, date, amount, desc, r_id, vendor, category in cur.fetchall():
        amount_display = f"${amount:.2f}" if amount else "N/A"
        print(f"  TX {tx_id} | {date} | {amount_display} | Receipt {r_id} | {vendor}")

cur.close()
conn.close()
