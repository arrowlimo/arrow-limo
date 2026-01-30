#!/usr/bin/env python3
"""
Investigate UNKNOWN receipts from verified_banking source.
These shouldn't exist if banking had proper descriptions.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 80)
print("INVESTIGATING UNKNOWN VERIFIED_BANKING RECEIPTS")
print("=" * 80)

# Get details of UNKNOWN receipts
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.gst_amount,
        r.description,
        r.vendor_name,
        r.source_system,
        r.source_reference,
        r.payment_method,
        r.document_type
    FROM receipts r
    WHERE r.vendor_name = 'UNKNOWN'
    ORDER BY r.receipt_date DESC
    LIMIT 100
""")

unknown_receipts = cur.fetchall()

print(f"\nTotal UNKNOWN receipts analyzed: {len(unknown_receipts)}")

# Analyze patterns
descriptions = {}
payment_methods = {}
document_types = {}
zero_amounts = 0
null_amounts = 0

for receipt in unknown_receipts:
    (receipt_id, receipt_date, gross_amount, gst_amount, description, 
     vendor_name, source_system, source_ref, payment_method, doc_type) = receipt
    
    # Count patterns
    desc_key = description or 'NULL'
    descriptions[desc_key] = descriptions.get(desc_key, 0) + 1
    
    pm_key = payment_method or 'NULL'
    payment_methods[pm_key] = payment_methods.get(pm_key, 0) + 1
    
    dt_key = doc_type or 'NULL'
    document_types[dt_key] = document_types.get(dt_key, 0) + 1
    
    if gross_amount is None:
        null_amounts += 1
    elif gross_amount == 0:
        zero_amounts += 1

print(f"\nAmount analysis:")
print(f"  NULL amounts: {null_amounts}")
print(f"  Zero amounts: {zero_amounts}")

print(f"\nTop 20 descriptions:")
for desc, count in sorted(descriptions.items(), key=lambda x: x[1], reverse=True)[:20]:
    print(f"  {count:4} | {desc}")

print(f"\nPayment methods:")
for pm, count in sorted(payment_methods.items(), key=lambda x: x[1], reverse=True):
    print(f"  {count:4} | {pm}")

print(f"\nDocument types:")
for dt, count in sorted(document_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {count:4} | {dt}")

# Check if these have banking transaction matches
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id)
    FROM receipts r
    INNER JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    WHERE r.vendor_name = 'UNKNOWN'
""")
matched_count = cur.fetchone()[0]

print(f"\nBanking match status:")
print(f"  Total UNKNOWN receipts: 1207")
print(f"  Have banking matches: {matched_count}")
print(f"  No banking matches: {1207 - matched_count}")

# Sample with banking match details
print("\n" + "=" * 80)
print("SAMPLE UNKNOWN RECEIPTS WITH BANKING DETAILS")
print("=" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.gross_amount,
        r.description as receipt_desc,
        b.description as banking_desc,
        b.vendor_extracted,
        b.debit_amount,
        b.credit_amount
    FROM receipts r
    INNER JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
    INNER JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
    WHERE r.vendor_name = 'UNKNOWN'
    LIMIT 20
""")

print("\nReceipt Desc          | Banking Desc                    | Banking Vendor")
print("-" * 80)
for row in cur.fetchall():
    r_desc = (row[3] or '')[:20]
    b_desc = (row[4] or '')[:35]
    b_vendor = (row[5] or 'NULL')[:25]
    print(f"{r_desc:20} | {b_desc:35} | {b_vendor}")

# Check for likely invalid entries
print("\n" + "=" * 80)
print("CHECKING FOR INVALID ENTRIES TO DELETE")
print("=" * 80)

# Deposits with no amount
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
      AND description IN ('DEPOSIT', 'Deposit', 'deposit', 'CASH DEPOSIT')
      AND (gross_amount IS NULL OR gross_amount = 0)
""")
deposit_count = cur.fetchone()[0]

# Credit memos
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
      AND (description LIKE '%CREDIT MEMO%' OR description LIKE '%Credit Memo%')
""")
credit_memo_count = cur.fetchone()[0]

# Email transfers
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE vendor_name = 'UNKNOWN'
      AND description LIKE '%EMAIL%'
""")
email_count = cur.fetchone()[0]

print(f"\nPotentially invalid entries:")
print(f"  Generic deposits (no amount): {deposit_count}")
print(f"  Credit memos: {credit_memo_count}")
print(f"  Email transfers: {email_count}")
print(f"\n⚠️  These appear to be journal entries or duplicates")
print(f"   Total to review for deletion: ~{deposit_count + credit_memo_count}")

cur.close()
conn.close()
