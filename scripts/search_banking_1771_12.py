"""
Search banking records for $1,771.12 around Jan-Apr 2012 dates.
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
print("BANKING RECORDS: $1,771.12 around Jan-Apr 2012")
print("=" * 120)

# Search for ALL transactions with this exact amount in early 2012
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
        bt.account_number,
        bt.debit_amount,
        bt.credit_amount,
        bt.balance,
        bt.description,
        bt.source_file,
        r.receipt_id,
        r.vendor_name,
        r.description as receipt_desc
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE (bt.debit_amount = 1771.12 OR bt.credit_amount = 1771.12)
      AND bt.transaction_date >= '2012-01-01'
      AND bt.transaction_date <= '2012-04-30'
    ORDER BY bt.transaction_date, bt.transaction_id
""")

transactions = cur.fetchall()

print(f"\nFound {len(transactions)} transactions with $1,771.12 in Jan-Apr 2012:\n")
print(f"{'TX':>6} | {'Date':10} | {'Posted':10} | {'Bank':7} | {'Account':15} | {'Debit':>10} | {'Credit':>10} | {'Balance':>11} | {'Receipt':>8} | Description")
print("-" * 165)

for tx_id, tx_date, posted, bank, acct, debit, credit, balance, desc, source, receipt_id, vendor, receipt_desc in transactions:
    debit_str = f"${debit:,.2f}" if debit else ""
    credit_str = f"${credit:,.2f}" if credit else ""
    balance_str = f"${balance:,.2f}" if balance else ""
    receipt_str = str(receipt_id) if receipt_id else "NONE"
    print(f"{tx_id:6d} | {tx_date} | {posted or 'N/A':10} | {bank:7} | {acct or 'N/A':15} | {debit_str:>10} | {credit_str:>10} | {balance_str:>11} | {receipt_str:>8} | {desc[:60]}")

# Group by date
print("\n\n" + "=" * 120)
print("GROUPED BY DATE")
print("=" * 120)

from collections import defaultdict
by_date = defaultdict(list)
for tx in transactions:
    by_date[tx[1]].append(tx)

for date in sorted(by_date.keys()):
    txs = by_date[date]
    print(f"\n{date} - {len(txs)} transactions:")
    for tx in txs:
        tx_id, tx_date, posted, bank, acct, debit, credit, balance, desc, source, receipt_id, vendor, receipt_desc = tx
        amount_type = f"DEBIT ${debit:,.2f}" if debit else f"CREDIT ${credit:,.2f}"
        receipt_str = f"Receipt {receipt_id} ({vendor})" if receipt_id else "NO RECEIPT"
        print(f"  TX {tx_id:6d} | {bank:7} | {amount_type:15} | {desc[:70]:70} | {receipt_str}")

# Now search for CHQ/CHEQUE references around these dates
print("\n\n" + "=" * 120)
print("ALL CHEQUE TRANSACTIONS: Jan-Apr 2012")
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
        bt.debit_amount,
        bt.credit_amount,
        bt.description,
        r.receipt_id
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE (bt.description ILIKE '%CHQ%' OR bt.description ILIKE '%CHEQUE%')
      AND bt.transaction_date >= '2012-01-01'
      AND bt.transaction_date <= '2012-04-30'
      AND (bt.debit_amount = 1771.12 OR bt.credit_amount = 1771.12)
    ORDER BY bt.transaction_date
""")

cheque_txs = cur.fetchall()
if cheque_txs:
    print(f"\nFound {len(cheque_txs)} cheque transactions with $1,771.12:\n")
    for tx_id, date, bank, debit, credit, desc, receipt_id in cheque_txs:
        amount = debit if debit else credit
        tx_type = "DEBIT" if debit else "CREDIT"
        receipt_str = f"Receipt {receipt_id}" if receipt_id else "NONE"
        print(f"  TX {tx_id:6d} | {date} | {bank:7} | ${amount:>10,.2f} {tx_type:6} | {desc[:60]:60} | {receipt_str:>8}")
else:
    print("No cheque transactions found with this amount")

# Check source files
print("\n\n" + "=" * 120)
print("SOURCE FILES FOR THESE TRANSACTIONS")
print("=" * 120)

sources = set(tx[9] for tx in transactions if tx[9])
if sources:
    for source in sorted(sources):
        count = sum(1 for tx in transactions if tx[9] == source)
        print(f"  {source}: {count} transactions")
else:
    print("No source files recorded")

cur.close()
conn.close()
