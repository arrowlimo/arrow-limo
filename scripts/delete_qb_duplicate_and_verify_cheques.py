"""
Delete QB duplicate TX 81373 and fix receipt link to real bank transaction TX 56865.
Then verify all CHQ entries.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("DELETE QB DUPLICATE AND FIX LINKS")
print("=" * 120)

# 1. Check current state
print("\n1. CURRENT STATE - TX 81373")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, 
           source_file, account_number
    FROM banking_transactions 
    WHERE transaction_id = 81373
""")
tx = cur.fetchone()
if tx:
    print(f"   TX {tx[0]} | {tx[1]} | {tx[3]} | {tx[2]} | Source: {tx[4]} | Account: {tx[5]}")
else:
    print("   ❌ TX 81373 not found")

# 2. Check receipt link
print("\n2. RECEIPT LINKED TO TX 81373")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id
    FROM receipts
    WHERE banking_transaction_id = 81373
""")
receipt = cur.fetchone()
if receipt:
    print(f"   Receipt {receipt[0]} | {receipt[1]} | ${receipt[2]:,.2f} | Linked to TX {receipt[3]}")
    receipt_id = receipt[0]
else:
    print("   ❌ No receipt linked to TX 81373")
    receipt_id = None

# 3. Update receipt to link to real bank transaction TX 56865
if receipt_id:
    print("\n3. UPDATING RECEIPT LINK: TX 81373 → TX 56865")
    cur.execute("""
        UPDATE receipts
        SET banking_transaction_id = 56865,
            receipt_source = 'Corrected - linked to bank statement transaction'
        WHERE receipt_id = %s
    """, (receipt_id,))
    print(f"   ✅ Updated receipt {receipt_id} to link to TX 56865 (bank statement)")

# 4. Delete QB duplicate TX 81373
print("\n4. DELETING QB DUPLICATE TX 81373")
cur.execute("""
    DELETE FROM banking_transactions
    WHERE transaction_id = 81373
""")
deleted = cur.rowcount
print(f"   ✅ Deleted {deleted} transaction(s)")

# Commit changes
conn.commit()
print("\n✅ CHANGES COMMITTED")

# 5. Verify ALL cheque transactions
print("\n\n" + "=" * 120)
print("VERIFICATION: ALL CHEQUE TRANSACTIONS")
print("=" * 120)

cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC'
            WHEN bt.bank_id = 2 THEN 'SCOTIA'
            ELSE 'Unknown'
        END as bank,
        bt.account_number,
        bt.debit_amount,
        bt.credit_amount,
        bt.description,
        r.receipt_id,
        r.vendor_name,
        CASE 
            WHEN bt.description ILIKE '%NSF%' THEN 'NSF'
            WHEN bt.description ILIKE '%RETURN%' THEN 'RETURN'
            ELSE ''
        END as nsf_flag
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.description ILIKE '%CHQ%' 
       OR bt.description ILIKE '%CHEQUE%'
    ORDER BY bt.transaction_date, bt.transaction_id
""")

all_cheques = cur.fetchall()

print(f"\nTotal cheque transactions: {len(all_cheques)}")

# Group by status
has_receipt = [t for t in all_cheques if t[7]]
no_receipt = [t for t in all_cheques if not t[7]]
nsf_transactions = [t for t in all_cheques if t[9]]

print(f"  - With receipts: {len(has_receipt)}")
print(f"  - Without receipts: {len(no_receipt)}")
print(f"  - NSF/RETURN transactions: {len(nsf_transactions)}")

# Show NSF transactions
if nsf_transactions:
    print("\n\nNSF/RETURN TRANSACTIONS:")
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Debit':>10} | {'Credit':>10} | {'Receipt':>8} | Description")
    print("-" * 120)
    for tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf in nsf_transactions:
        debit_str = f"${debit:,.2f}" if debit else ""
        credit_str = f"${credit:,.2f}" if credit else ""
        receipt_str = str(receipt_id) if receipt_id else "NONE"
        print(f"{tx_id:6d} | {date} | {bank:7} | {debit_str:>10} | {credit_str:>10} | {receipt_str:>8} | {desc[:60]}")

# Show transactions WITHOUT receipts (excluding NSF)
no_receipt_non_nsf = [t for t in no_receipt if not t[9]]
if no_receipt_non_nsf:
    print(f"\n\nNON-NSF CHEQUE TRANSACTIONS WITHOUT RECEIPTS: {len(no_receipt_non_nsf)}")
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Debit':>10} | {'Credit':>10} | Description")
    print("-" * 120)
    for tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf in no_receipt_non_nsf[:20]:
        debit_str = f"${debit:,.2f}" if debit else ""
        credit_str = f"${credit:,.2f}" if credit else ""
        print(f"{tx_id:6d} | {date} | {bank:7} | {debit_str:>10} | {credit_str:>10} | {desc[:70]}")
    if len(no_receipt_non_nsf) > 20:
        print(f"  ... and {len(no_receipt_non_nsf) - 20} more")

# Show sample of transactions WITH receipts
print(f"\n\nSAMPLE CHEQUE TRANSACTIONS WITH RECEIPTS:")
print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Amount':>10} | {'Receipt':>8} | Vendor / Description")
print("-" * 120)
for tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf in has_receipt[:15]:
    amount = debit if debit else credit
    print(f"{tx_id:6d} | {date} | {bank:7} | ${amount:>9,.2f} | {receipt_id:8d} | {vendor or desc[:60]}")

# Check for duplicate CHQ numbers
print("\n\n" + "=" * 120)
print("DUPLICATE CHEQUE NUMBER CHECK")
print("=" * 120)

import re
cheque_pattern = re.compile(r'CHQ\s*(\d+)', re.IGNORECASE)

cheques_by_number = {}
for tx in all_cheques:
    tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf = tx
    match = cheque_pattern.search(desc)
    if match:
        chq_num = int(match.group(1))
        key = (chq_num, bank)
        if key not in cheques_by_number:
            cheques_by_number[key] = []
        cheques_by_number[key].append(tx)

# Find duplicates (same cheque number, same bank, same date)
print("\nCHEQUE NUMBER USAGE BY BANK:")
cibc_nums = set(k[0] for k in cheques_by_number.keys() if k[1] == 'CIBC')
scotia_nums = set(k[0] for k in cheques_by_number.keys() if k[1] == 'SCOTIA')
unknown_nums = set(k[0] for k in cheques_by_number.keys() if k[1] == 'Unknown')

print(f"  CIBC: {len(cibc_nums)} unique cheque numbers")
print(f"  SCOTIA: {len(scotia_nums)} unique cheque numbers")
print(f"  Unknown: {len(unknown_nums)} unique cheque numbers")

overlap = cibc_nums & scotia_nums
if overlap:
    print(f"\n⚠️  {len(overlap)} cheque numbers used in both CIBC and SCOTIA:")
    for num in sorted(overlap)[:10]:
        print(f"    CHQ #{num}")
else:
    print("\n✅ No overlap - cheque numbers are unique per bank")

# Check for same date+amount duplicates
print("\n\nCHECKING FOR SAME-DATE DUPLICATE DEBITS:")
from collections import defaultdict
by_date_amount = defaultdict(list)

for tx in all_cheques:
    tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf = tx
    if debit:  # Only check debits (actual cheques)
        key = (date, debit, bank)
        by_date_amount[key].append(tx)

duplicates = {k: v for k, v in by_date_amount.items() if len(v) > 1}
if duplicates:
    print(f"Found {len(duplicates)} potential duplicate sets:\n")
    for (date, amount, bank), txs in list(duplicates.items())[:10]:
        print(f"  {date} | {bank} | ${amount:,.2f} - {len(txs)} transactions:")
        for tx in txs:
            tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf = tx
            receipt_str = f"Receipt {receipt_id}" if receipt_id else "NO RECEIPT"
            print(f"    TX {tx_id:6d} | {desc[:70]:70} | {receipt_str}")
else:
    print("✅ No same-date duplicate debits found")

print("\n" + "=" * 120)
print("VERIFICATION COMPLETE")
print("=" * 120)

cur.close()
conn.close()
