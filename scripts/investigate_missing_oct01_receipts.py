#!/usr/bin/env python3
"""
Investigate why Oct 1, 2012 Scotia transactions don't have receipts
despite "fully matched" status claim.
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
print("INVESTIGATING MISSING RECEIPTS FOR SCOTIA OCT 1, 2012")
print("=" * 80)

# 1. Check when receipts were created for Scotia Bank
print("\n1. RECEIPT CREATION TIMELINE FOR SCOTIA BANK:")
print("-" * 80)

cur.execute("""
    SELECT 
        DATE_TRUNC('month', r.receipt_date)::date as month,
        COUNT(*) as receipt_count
    FROM receipts r
    WHERE r.mapped_bank_account_id = 2
      AND r.receipt_date >= '2012-01-01' AND r.receipt_date <= '2012-12-31'
    GROUP BY DATE_TRUNC('month', r.receipt_date)
    ORDER BY month
""")

print("\nScotia Bank receipts created in 2012 (by month):")
for month, count in cur.fetchall():
    print(f"  {month}: {count:4} receipts")

# 2. Check Oct 2012 specifically
print("\n\n2. SCOTIA BANK OCTOBER 2012 ANALYSIS:")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) as total_transactions
    FROM banking_transactions
    WHERE bank_id = 2
      AND transaction_date >= '2012-10-01' AND transaction_date <= '2012-10-31'
""")
total_oct = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) as with_receipts
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.bank_id = 2
      AND bt.transaction_date >= '2012-10-01' AND bt.transaction_date <= '2012-10-31'
""")
with_receipts = cur.fetchone()[0]

print(f"Total Scotia transactions in Oct 2012: {total_oct}")
print(f"With receipts: {with_receipts}")
print(f"WITHOUT receipts: {total_oct - with_receipts}")
print(f"Match rate: {(with_receipts/total_oct*100) if total_oct > 0 else 0:.1f}%")

# 3. Check if receipts exist but not linked
print("\n\n3. CHECK FOR UNLINKED RECEIPTS (Oct 1, 2012):")
print("-" * 80)

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date, banking_transaction_id
    FROM receipts
    WHERE mapped_bank_account_id = 2
      AND receipt_date = '2012-10-01'
    ORDER BY receipt_id
""")

oct1_receipts = cur.fetchall()
print(f"Receipts with date Oct 1, 2012: {len(oct1_receipts)}")

if oct1_receipts:
    print("\nReceipts found:")
    for r_id, vendor, amount, date, bt_id in oct1_receipts:
        link_status = f"Linked to TX {bt_id}" if bt_id else "NOT LINKED"
        print(f"  Receipt {r_id:6d} | ${amount:>10,.2f} | {vendor[:30]:30} | {link_status}")

# 4. Check receipt creation method
print("\n\n4. RECEIPT CREATION SOURCE:")
print("-" * 80)

cur.execute("""
    SELECT DISTINCT created_from_banking
    FROM receipts
    WHERE mapped_bank_account_id = 2
      AND receipt_date >= '2012-10-01' AND receipt_date <= '2012-10-31'
""")

for (created_from,) in cur.fetchall():
    print(f"  created_from_banking: {created_from}")

# 5. Check for any exclusion criteria
print("\n\n5. OCT 1 TRANSACTIONS - WHY NO RECEIPTS?")
print("-" * 80)

cur.execute("""
    SELECT transaction_id, debit_amount, credit_amount, description,
           reconciliation_status, balance_verified
    FROM banking_transactions
    WHERE bank_id = 2
      AND transaction_date = '2012-10-01'
    ORDER BY transaction_id
""")

print("\nChecking each transaction:")
for tx_id, debit, credit, desc, status, verified in cur.fetchall():
    amount = debit if debit else credit
    tx_type = 'DEBIT' if debit else 'CREDIT'
    
    # Check if receipt exists
    cur.execute("""
        SELECT receipt_id FROM receipts WHERE banking_transaction_id = %s
    """, (tx_id,))
    
    receipt = cur.fetchone()
    
    if not receipt:
        print(f"  TX {tx_id:6d} | {tx_type:6} | ${amount:>10,.2f} | NO RECEIPT")
        print(f"    Description: {desc[:50]}")
        print(f"    Status: {status or 'None'} | Verified: {verified}")

# 6. Check if there was a date filter on receipt creation
print("\n\n6. LOOKING FOR RECEIPT CREATION SCRIPTS:")
print("-" * 80)

import glob
scripts = glob.glob("L:/limo/scripts/*create*receipt*.py")
scripts.extend(glob.glob("L:/limo/scripts/*auto*receipt*.py"))
scripts.extend(glob.glob("L:/limo/scripts/*generate*receipt*.py"))

if scripts:
    print("Found receipt creation scripts:")
    for script in scripts[:10]:
        print(f"  {script}")
else:
    print("No receipt creation scripts found")

cur.close()
conn.close()
