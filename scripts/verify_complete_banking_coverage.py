#!/usr/bin/env python3
"""
Verify EVERY banking transaction has a matching receipt.
Also search for specific cheque: CHQ 202, $1771.12, CARLA METIRIER, Jan 03 2012
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
print("BANKING TRANSACTION COVERAGE VERIFICATION")
print("=" * 80)

# 1. Check specific cheque mentioned by user
print("\n1. SEARCHING FOR SPECIFIC CHEQUE: CHQ 202, $1771.12, Jan 2012")
print("-" * 80)

cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.description,
        r.payment_method
    FROM receipts r
    WHERE (r.gross_amount BETWEEN 1771.00 AND 1771.20
       OR r.gross_amount BETWEEN 1770.00 AND 1772.00)
      AND r.receipt_date BETWEEN '2012-01-01' AND '2012-01-31'
    ORDER BY ABS(r.gross_amount - 1771.12)
    LIMIT 10
""")

cheque_matches = cur.fetchall()
if cheque_matches:
    print(f"Found {len(cheque_matches)} possible matches:")
    for receipt_id, date, vendor, amount, desc, payment in cheque_matches:
        print(f"\n  Receipt {receipt_id} | {date} | ${amount:,.2f} | {payment}")
        print(f"    Vendor: {vendor}")
        print(f"    Description: {desc}")
else:
    print("❌ NO MATCH FOUND - checking banking transactions...")
    
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.credit_amount
        FROM banking_transactions bt
        WHERE (bt.debit_amount BETWEEN 1770 AND 1772
           OR bt.credit_amount BETWEEN 1770 AND 1772)
          AND bt.transaction_date BETWEEN '2012-01-01' AND '2012-01-31'
        LIMIT 10
    """)
    
    banking_matches = cur.fetchall()
    if banking_matches:
        print(f"Found {len(banking_matches)} banking transactions:")
        for tx_id, date, desc, debit, credit in banking_matches:
            amount = debit or credit
            tx_type = "DEBIT" if debit else "CREDIT"
            print(f"  TX {tx_id} | {date} | ${amount:,.2f} {tx_type} | {desc[:60]}")

# 2. Check ALL banking transactions have receipts
print("\n\n2. COMPLETE BANKING TRANSACTION COVERAGE")
print("-" * 80)

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(brml.banking_transaction_id) as matched,
        COUNT(*) - COUNT(brml.banking_transaction_id) as unmatched
    FROM banking_transactions bt
    LEFT JOIN banking_receipt_matching_ledger brml ON bt.transaction_id = brml.banking_transaction_id
    WHERE bt.debit_amount IS NOT NULL AND bt.debit_amount > 0
""")

total, matched, unmatched = cur.fetchone()
match_pct = (matched / total * 100) if total > 0 else 0

print(f"\nDEBIT Transactions (money OUT):")
print(f"  Total: {total:,}")
print(f"  Matched to receipts: {matched:,} ({match_pct:.2f}%)")
print(f"  Unmatched: {unmatched:,}")

cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(brml.banking_transaction_id) as matched,
        COUNT(*) - COUNT(brml.banking_transaction_id) as unmatched
    FROM banking_transactions bt
    LEFT JOIN banking_receipt_matching_ledger brml ON bt.transaction_id = brml.banking_transaction_id
    WHERE bt.credit_amount IS NOT NULL AND bt.credit_amount > 0
""")

total_cr, matched_cr, unmatched_cr = cur.fetchone()
match_pct_cr = (matched_cr / total_cr * 100) if total_cr > 0 else 0

print(f"\nCREDIT Transactions (money IN):")
print(f"  Total: {total_cr:,}")
print(f"  Matched to receipts: {matched_cr:,} ({match_pct_cr:.2f}%)")
print(f"  Unmatched: {unmatched_cr:,}")

# 3. Check cheque transactions specifically
print("\n\n3. CHEQUE TRANSACTION COVERAGE")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE payment_method LIKE '%CHQ%'
       OR payment_method LIKE '%CHEQUE%'
       OR payment_method LIKE '%CHECK%'
       OR description LIKE '%CHQ%'
       OR description LIKE '%CHEQUE%'
       OR description LIKE '%CHECK%'
""")

total_cheques = cur.fetchone()[0]
print(f"Total cheque receipts in database: {total_cheques:,}")

# Sample cheque receipts
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        description,
        payment_method
    FROM receipts
    WHERE description LIKE '%CHQ%'
       OR description LIKE '%CHEQUE%'
       OR payment_method LIKE '%CHQ%'
    ORDER BY receipt_date
    LIMIT 20
""")

print("\nSample cheque receipts:")
for receipt_id, date, vendor, amount, desc, payment in cur.fetchall():
    vendor_display = vendor[:30] if vendor else "None"
    amount_display = amount if amount is not None else 0.0
    desc_display = desc[:40] if desc else (payment[:40] if payment else "None")
    print(f"  {receipt_id} | {date} | {vendor_display:30} | ${amount_display:>10,.2f} | {desc_display}")

# 4. Summary
print("\n\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

if match_pct > 99:
    print(f"\n✅ EXCELLENT: {match_pct:.2f}% of banking debits have matching receipts")
else:
    print(f"\n⚠️  WARNING: Only {match_pct:.2f}% of banking debits have matching receipts")
    print(f"   {unmatched:,} transactions ({unmatched/(total+total_cr)*100:.1f}% of all transactions) are unmatched")

if unmatched > 0:
    print(f"\n📋 Top 10 unmatched debit transactions:")
    cur.execute("""
        SELECT 
            bt.transaction_date,
            bt.description,
            bt.debit_amount
        FROM banking_transactions bt
        LEFT JOIN banking_receipt_matching_ledger brml ON bt.transaction_id = brml.banking_transaction_id
        WHERE brml.banking_transaction_id IS NULL
          AND bt.debit_amount > 0
        ORDER BY bt.debit_amount DESC
        LIMIT 10
    """)
    
    for date, desc, amount in cur.fetchall():
        print(f"  {date} | ${amount:>12,.2f} | {desc[:60]}")

print(f"\n💰 Total cheque receipts: {total_cheques:,}")

cur.close()
conn.close()
