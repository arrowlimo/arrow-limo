"""
Mark QB duplicate TX 81373 as duplicate (can't delete - 2012 locked).
Then verify all CHQ entries.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 120)
print("MARK QB DUPLICATE AND FIX LINKS (2012 is locked)")
print("=" * 120)

# 1. Receipt link already updated to TX 56865
print("\n1. VERIFY RECEIPT LINK")
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id
    FROM receipts
    WHERE receipt_id = 139332
""")
receipt = cur.fetchone()
if receipt:
    print(f"   Receipt {receipt[0]} | {receipt[1]} | ${receipt[2]:,.2f} | Linked to TX {receipt[3]}")
    if receipt[3] == 56865:
        print("   ✅ Correctly linked to TX 56865 (bank statement)")
    else:
        print(f"   ⚠️  Still linked to TX {receipt[3]}")

# 2. Mark TX 81373 as duplicate/reconciled
print("\n2. MARKING TX 81373 AS DUPLICATE")
cur.execute("""
    UPDATE banking_transactions
    SET reconciliation_status = 'DUPLICATE',
        reconciliation_notes = 'Duplicate of TX 56865 (same CHQ 203 Metuier $1771.12 Jan 4 2012). QB import duplicate.',
        reconciled_at = NOW(),
        reconciled_by = 'System - duplicate cleanup'
    WHERE transaction_id = 81373
""")
print(f"   ✅ Marked TX 81373 as DUPLICATE")

# Commit
conn.commit()
print("\n✅ CHANGES COMMITTED")

# 3. Verify ALL cheque transactions
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
        END as nsf_flag,
        bt.reconciliation_status
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE (bt.description ILIKE '%CHQ%' OR bt.description ILIKE '%CHEQUE%')
      AND COALESCE(bt.reconciliation_status, '') != 'DUPLICATE'
    ORDER BY bt.transaction_date, bt.transaction_id
""")

all_cheques = cur.fetchall()

print(f"\nTotal active (non-duplicate) cheque transactions: {len(all_cheques)}")

# Group by status
has_receipt = [t for t in all_cheques if t[7]]
no_receipt = [t for t in all_cheques if not t[7]]
nsf_transactions = [t for t in all_cheques if t[9]]
debit_tx = [t for t in all_cheques if t[4]]  # Has debit amount
credit_tx = [t for t in all_cheques if t[5]]  # Has credit amount

print(f"  - With receipts: {len(has_receipt)}")
print(f"  - Without receipts: {len(no_receipt)}")
print(f"  - NSF/RETURN transactions: {len(nsf_transactions)}")
print(f"  - DEBIT (money out): {len(debit_tx)}")
print(f"  - CREDIT (money in): {len(credit_tx)}")

# Show NSF transactions
if nsf_transactions:
    print("\n\nNSF/RETURN TRANSACTIONS:")
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Debit':>10} | {'Credit':>10} | {'Receipt':>8} | Description")
    print("-" * 120)
    for tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf, recon in nsf_transactions:
        debit_str = f"${debit:,.2f}" if debit else ""
        credit_str = f"${credit:,.2f}" if credit else ""
        receipt_str = str(receipt_id) if receipt_id else "NONE"
        print(f"{tx_id:6d} | {date} | {bank:7} | {debit_str:>10} | {credit_str:>10} | {receipt_str:>8} | {desc[:60]}")

# Show DEBIT transactions WITHOUT receipts (excluding NSF)
debit_no_receipt = [t for t in debit_tx if not t[7] and not t[9]]
if debit_no_receipt:
    print(f"\n\nNON-NSF DEBIT CHEQUES WITHOUT RECEIPTS: {len(debit_no_receipt)}")
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Debit':>10} | Description")
    print("-" * 120)
    for tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf, recon in debit_no_receipt[:30]:
        print(f"{tx_id:6d} | {date} | {bank:7} | ${debit:>9,.2f} | {desc[:80]}")
    if len(debit_no_receipt) > 30:
        print(f"  ... and {len(debit_no_receipt) - 30} more")

# Show CREDIT transactions (these are QuickBooks journal entries, don't need receipts)
if credit_tx:
    print(f"\n\nCREDIT CHEQUE TRANSACTIONS (QuickBooks journal entries): {len(credit_tx)}")
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Credit':>10} | {'Receipt':>8} | Description")
    print("-" * 120)
    for tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf, recon in credit_tx[:20]:
        receipt_str = str(receipt_id) if receipt_id else "NONE"
        print(f"{tx_id:6d} | {date} | {bank:7} | ${credit:>9,.2f} | {receipt_str:>8} | {desc[:70]}")
    if len(credit_tx) > 20:
        print(f"  ... and {len(credit_tx) - 20} more")

# Show sample WITH receipts
print(f"\n\nSAMPLE DEBIT CHEQUES WITH RECEIPTS:")
print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Amount':>10} | {'Receipt':>8} | Vendor")
print("-" * 120)
debit_with_receipt = [t for t in has_receipt if t[4]]
for tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf, recon in debit_with_receipt[:15]:
    print(f"{tx_id:6d} | {date} | {bank:7} | ${debit:>9,.2f} | {receipt_id:8d} | {vendor or desc[:60]}")

# Check for duplicate CHQ numbers
print("\n\n" + "=" * 120)
print("CHEQUE NUMBER ANALYSIS")
print("=" * 120)

import re
cheque_pattern = re.compile(r'CHQ\s*(\d+)', re.IGNORECASE)

cheques_by_number = {}
for tx in all_cheques:
    tx_id, date, bank, acct, debit, credit, desc, receipt_id, vendor, nsf, recon = tx
    match = cheque_pattern.search(desc)
    if match:
        chq_num = int(match.group(1))
        key = (chq_num, bank)
        if key not in cheques_by_number:
            cheques_by_number[key] = []
        cheques_by_number[key].append(tx)

cibc_nums = set(k[0] for k in cheques_by_number.keys() if k[1] == 'CIBC')
scotia_nums = set(k[0] for k in cheques_by_number.keys() if k[1] == 'SCOTIA')
unknown_nums = set(k[0] for k in cheques_by_number.keys() if k[1] == 'Unknown')

print(f"  CIBC: {len(cibc_nums)} unique cheque numbers")
print(f"  SCOTIA: {len(scotia_nums)} unique cheque numbers")
print(f"  Unknown: {len(unknown_nums)} unique cheque numbers")

overlap = cibc_nums & scotia_nums
if overlap:
    print(f"\n✅ {len(overlap)} cheque numbers used in both banks (expected - different cheque books):")
    for num in sorted(overlap)[:10]:
        cibc_txs = cheques_by_number.get((num, 'CIBC'), [])
        scotia_txs = cheques_by_number.get((num, 'SCOTIA'), [])
        print(f"  CHQ #{num}:")
        for tx in cibc_txs:
            print(f"    CIBC:   {tx[1]} | ${tx[4] or tx[5]:,.2f}")
        for tx in scotia_txs:
            print(f"    SCOTIA: {tx[1]} | ${tx[4] or tx[5]:,.2f}")
    if len(overlap) > 10:
        print(f"  ... and {len(overlap) - 10} more")

# Summary
print("\n\n" + "=" * 120)
print("SUMMARY")
print("=" * 120)
print(f"Total active cheque transactions: {len(all_cheques)}")
print(f"  DEBIT (actual cheques): {len(debit_tx)}")
print(f"    - With receipts: {len([t for t in debit_tx if t[7]])}")
print(f"    - Without receipts (non-NSF): {len(debit_no_receipt)}")
print(f"    - NSF/RETURN: {len([t for t in nsf_transactions if t[4]])}")
print(f"  CREDIT (QB journal entries): {len(credit_tx)}")
print(f"    - These are bookkeeping entries, don't need receipts")

print("\n✅ VERIFICATION COMPLETE")

cur.close()
conn.close()
