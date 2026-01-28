#!/usr/bin/env python
"""
Find Banking Transactions Without Linked Receipts
Shows "orphaned" payments that need invoices added
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("UNMATCHED BANKING TRANSACTIONS (Payments Without Receipts)")
print("=" * 80)

# Find Fibrenew 2014 banking transactions without receipts
print("\n1. Fibrenew 2014 Banking Transactions:")
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.check_number,
        bt.account_number,
        r.receipt_id,
        r.gross_amount as receipt_amount,
        CASE 
            WHEN r.receipt_id IS NULL THEN '❌ NO RECEIPT'
            ELSE '✅ HAS RECEIPT'
        END as match_status
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.description ILIKE '%fibr%'
        AND EXTRACT(YEAR FROM bt.transaction_date) = 2014
    ORDER BY bt.transaction_date
""")
fibrenew_2014 = cur.fetchall()

unmatched_count = 0
matched_count = 0

if fibrenew_2014:
    print(f"\nFound {len(fibrenew_2014)} Fibrenew banking transaction(s) in 2014:\n")
    for b in fibrenew_2014:
        print(f"Banking ID: {b[0]} | Date: {b[1]} | Amount: ${b[3]:,.2f}")
        print(f"Check: {b[4]} | Account: {b[5]}")
        print(f"Description: {b[2]}")
        print(f"Status: {b[8]}")
        if b[6]:  # Has receipt
            print(f"  → Linked to Receipt ID: {b[6]} (${b[7]:,.2f})")
            matched_count += 1
        else:
            print(f"  → ⚠️ NO RECEIPT LINKED - Need to add invoice!")
            unmatched_count += 1
        print("-" * 80)
    
    print(f"\n📊 SUMMARY:")
    print(f"  ✅ Matched (have receipts): {matched_count}")
    print(f"  ❌ Unmatched (need receipts): {unmatched_count}")

# Find ALL unmatched banking transactions (could be large amounts needing invoices)
print("\n\n2. ALL Unmatched Banking Transactions in 2014 (Top 50 by amount):")
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.check_number,
        bt.vendor_extracted
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE r.receipt_id IS NULL
        AND bt.debit_amount > 0
        AND EXTRACT(YEAR FROM bt.transaction_date) = 2014
    ORDER BY bt.debit_amount DESC
    LIMIT 50
""")
all_unmatched = cur.fetchall()

if all_unmatched:
    print(f"\n❌ Found {len(all_unmatched)} unmatched transactions (showing top 50):\n")
    total_unmatched_amount = 0
    for b in all_unmatched:
        print(f"ID: {b[0]:6d} | {b[1]} | ${b[3]:>10,.2f} | Check: {b[4] or 'N/A':10s} | Vendor: {b[5] or 'N/A':20s}")
        print(f"  {b[2][:75]}")
        total_unmatched_amount += b[3]
    
    print(f"\n💰 Total Unmatched Amount (top 50): ${total_unmatched_amount:,.2f}")

# Find receipts linked to the specific Fibrenew banking transactions
print("\n\n3. Details of Fibrenew Receipts (if any):")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.description,
        r.source_reference,
        r.banking_transaction_id,
        bt.debit_amount as banking_amount,
        bt.check_number
    FROM receipts r
    INNER JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name ILIKE '%fibr%'
        AND EXTRACT(YEAR FROM r.receipt_date) = 2014
    ORDER BY r.receipt_date
""")
fibrenew_receipts = cur.fetchall()

if fibrenew_receipts:
    print(f"\n✅ Found {len(fibrenew_receipts)} Fibrenew receipt(s) with banking links:")
    for r in fibrenew_receipts:
        print(f"\nReceipt ID: {r[0]}")
        print(f"Date: {r[1]} | Amount: ${r[3]:,.2f}")
        print(f"Vendor: {r[2]}")
        print(f"Description: {r[4] or 'N/A'}")
        print(f"Invoice/Ref: {r[5] or 'N/A'}")
        print(f"Banking TX: {r[6]} (Check {r[8]}, Amount: ${r[7]:,.2f})")
else:
    print("\n❌ No Fibrenew receipts with banking links found")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("INSTRUCTIONS:")
print("  1. Unmatched transactions show as '❌ NO RECEIPT'")
print("  2. Use Receipt Search & Match widget to:")
print("     - Search by Banking Transaction ID")
print("     - Add receipt and link to that banking ID")
print("  3. For Fibrenew, the large payments likely cover multiple invoices")
print("     - Add each invoice separately, all linked to same banking TX ID")
print("=" * 80)
