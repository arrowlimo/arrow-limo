"""
Check if Metuier transactions are duplicates or NSF-related.
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("METUIER/METIRIER TRANSACTION ANALYSIS")
print("=" * 80)

# Get ALL transactions for Metuier
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.posted_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC'
            WHEN bt.bank_id = 2 THEN 'SCOTIA'
            ELSE 'Unknown'
        END as bank,
        bt.debit_amount,
        bt.credit_amount,
        bt.balance,
        bt.description,
        bt.source_file,
        r.receipt_id,
        r.vendor_name
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.description ILIKE '%METUI%' 
       OR bt.description ILIKE '%METIRI%'
    ORDER BY bt.transaction_date, bt.transaction_id
""")

transactions = cur.fetchall()

print(f"\nFound {len(transactions)} Metuier/Metirier transactions:\n")
print(f"{'TX ID':>6} | {'Date':10} | {'Posted':10} | {'Bank':7} | {'Debit':>10} | {'Credit':>10} | {'Balance':>10} | {'Receipt':>8} | Description")
print("-" * 150)

for tx_id, tx_date, posted, bank, debit, credit, balance, desc, source, receipt_id, vendor in transactions:
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    balance_str = f"${balance:,.2f}" if balance else ""
    receipt_str = str(receipt_id) if receipt_id else "NONE"
    print(f"{tx_id:6d} | {tx_date} | {posted or 'N/A':10} | {bank:7} | {debit_str:>10} | {credit_str:>10} | {balance_str:>10} | {receipt_str:>8} | {desc[:70]}")

# Check for NSF patterns
print("\n\n" + "=" * 80)
print("NSF ANALYSIS")
print("=" * 80)

nsf_count = sum(1 for t in transactions if 'NSF' in t[7].upper() or 'RETURN' in t[7].upper())
print(f"Transactions with NSF/RETURN in description: {nsf_count}")

# Check for duplicates (same date + same amount)
print("\n\n" + "=" * 80)
print("DUPLICATE ANALYSIS")
print("=" * 80)

from collections import defaultdict
by_date_amount = defaultdict(list)

for tx in transactions:
    tx_id, tx_date, posted, bank, debit, credit, balance, desc, source, receipt_id, vendor = tx
    amount = debit if debit else credit
    key = (tx_date, amount, 'DEBIT' if debit else 'CREDIT')
    by_date_amount[key].append(tx)

duplicates = {k: v for k, v in by_date_amount.items() if len(v) > 1}

if duplicates:
    print(f"Found {len(duplicates)} sets of duplicate date+amount combinations:\n")
    for (date, amount, tx_type), txs in duplicates.items():
        print(f"\n{date} | {tx_type} ${amount:,.2f} - {len(txs)} transactions:")
        for tx in txs:
            tx_id, tx_date, posted, bank, debit, credit, balance, desc, source, receipt_id, vendor = tx
            receipt_str = f"Receipt {receipt_id}" if receipt_id else "NO RECEIPT"
            print(f"  TX {tx_id:6d} | {bank:7} | {desc[:60]:60} | {receipt_str}")
else:
    print("✅ No duplicates found - all transactions have unique date+amount+type combinations")

# Check the specific 3 transactions we saw
print("\n\n" + "=" * 80)
print("SPECIFIC TRANSACTIONS: TX 80354, 80628, 81373")
print("=" * 80)

cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC'
            WHEN bt.bank_id = 2 THEN 'SCOTIA'
            ELSE 'Unknown'
        END as bank,
        bt.debit_amount,
        bt.credit_amount,
        bt.description,
        r.receipt_id,
        r.vendor_name
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.transaction_id IN (80354, 80628, 81373)
    ORDER BY bt.transaction_id
""")

print("\nThese 3 transactions:")
for tx_id, date, bank, debit, credit, desc, receipt_id, vendor in cur.fetchall():
    amount = debit if debit else credit
    tx_type = "DEBIT" if debit else "CREDIT"
    receipt_str = f"Receipt {receipt_id} ({vendor})" if receipt_id else "NO RECEIPT"
    print(f"  TX {tx_id:6d} | {date} | {bank:7} | ${amount:>10,.2f} {tx_type:6} | {desc[:50]:50} | {receipt_str}")

cur.close()
conn.close()
