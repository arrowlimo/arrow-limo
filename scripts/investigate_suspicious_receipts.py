#!/usr/bin/env python3
"""
Investigate suspicious receipt patterns flagged by user:

1. Monthly summaries - should these be journal entries instead of receipts?
2. Journal entries in receipts - what are these?
3. Cash receipts not in banking - legitimate or missing?
4. Large withdrawals not in banking - bugus or missing?
"""

import psycopg2
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("INVESTIGATING SUSPICIOUS RECEIPT PATTERNS")
    print("=" * 80)
    
    # Issue 1: Monthly summaries in receipts
    print("\n1. MONTHLY SUMMARIES - Should these be journal entries?")
    print("-" * 80)
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.category,
            r.gross_amount,
            r.description,
            r.payment_method,
            CASE WHEN brml.receipt_id IS NOT NULL THEN 'YES' ELSE 'NO' END as in_banking
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        WHERE r.description LIKE '%summary%'
           OR r.description LIKE '%month%'
           OR r.vendor_name LIKE '%SUMMARY%'
           OR r.vendor_name LIKE '%MONTH%'
        ORDER BY r.gross_amount DESC
        LIMIT 50
    """)
    
    summaries = cur.fetchall()
    print(f"Found {len(summaries)} receipts with 'summary' or 'month' in description/vendor")
    
    total_amount = 0
    in_banking_count = 0
    for receipt_id, date, vendor, category, amount, desc, payment, in_banking in summaries:
        total_amount += amount
        if in_banking == 'YES':
            in_banking_count += 1
        print(f"  {receipt_id} | {date} | {vendor[:30]:30} | ${amount:>12,.2f} | Banking: {in_banking}")
        if desc:
            print(f"       Description: {desc[:70]}")
    
    print(f"\nTotal: {len(summaries)} receipts, ${total_amount:,.2f}")
    print(f"In banking: {in_banking_count}/{len(summaries)} ({100*in_banking_count/len(summaries) if summaries else 0:.1f}%)")
    
    # Issue 2: Journal entries in receipts
    print("\n\n2. JOURNAL ENTRIES - What are these doing in receipts?")
    print("-" * 80)
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.category,
            r.gross_amount,
            r.description,
            r.payment_method,
            CASE WHEN brml.receipt_id IS NOT NULL THEN 'YES' ELSE 'NO' END as in_banking
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        WHERE r.vendor_name LIKE '%JOURNAL%'
           OR r.description LIKE '%JOURNAL%'
           OR r.payment_method = 'JOURNAL'
        ORDER BY r.gross_amount DESC
    """)
    
    journals = cur.fetchall()
    print(f"Found {len(journals)} receipts with 'JOURNAL' in vendor/description/payment")
    
    total_journal = 0
    in_banking_j = 0
    for receipt_id, date, vendor, category, amount, desc, payment, in_banking in journals:
        total_journal += amount
        if in_banking == 'YES':
            in_banking_j += 1
        print(f"  {receipt_id} | {date} | {vendor[:30]:30} | ${amount:>12,.2f} | Banking: {in_banking}")
        if desc:
            print(f"       Description: {desc[:70]}")
        print(f"       Payment: {payment}")
    
    print(f"\nTotal: {len(journals)} receipts, ${total_journal:,.2f}")
    print(f"In banking: {in_banking_j}/{len(journals)} ({100*in_banking_j/len(journals) if journals else 0:.1f}%)")
    
    # Issue 3: Cash receipts not in banking (over $1000)
    print("\n\n3. LARGE CASH RECEIPTS NOT IN BANKING - Missing or legitimate?")
    print("-" * 80)
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.category,
            r.gross_amount,
            r.description,
            r.payment_method
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        WHERE brml.receipt_id IS NULL
          AND r.payment_method IN ('CASH', 'CHEQUE', 'CHECK')
          AND r.gross_amount > 1000
        ORDER BY r.gross_amount DESC
        LIMIT 50
    """)
    
    cash_missing = cur.fetchall()
    print(f"Found {len(cash_missing)} large cash/cheque receipts NOT in banking (>$1000)")
    
    total_cash = 0
    for receipt_id, date, vendor, category, amount, desc, payment in cash_missing:
        total_cash += amount
        print(f"  {receipt_id} | {date} | {vendor[:30]:30} | ${amount:>12,.2f} | {payment}")
        if desc:
            print(f"       Description: {desc[:70]}")
    
    print(f"\nTotal: {len(cash_missing)} receipts, ${total_cash:,.2f}")
    
    # Issue 4: Large withdrawals not in banking
    print("\n\n4. LARGE WITHDRAWALS - Should be in banking or bogus?")
    print("-" * 80)
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.category,
            r.gross_amount,
            r.description,
            r.payment_method,
            CASE WHEN brml.receipt_id IS NOT NULL THEN 'YES' ELSE 'NO' END as in_banking
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger brml ON r.receipt_id = brml.receipt_id
        WHERE (r.description LIKE '%withdrawal%'
           OR r.description LIKE '%withdraw%'
           OR r.vendor_name LIKE '%WITHDRAWAL%'
           OR r.vendor_name LIKE '%ATM%'
           OR r.vendor_name LIKE '%CASH%')
          AND r.gross_amount > 1000
        ORDER BY r.gross_amount DESC
        LIMIT 50
    """)
    
    withdrawals = cur.fetchall()
    print(f"Found {len(withdrawals)} large withdrawal-like receipts (>$1000)")
    
    total_wd = 0
    in_banking_wd = 0
    not_in_banking_wd = 0
    for receipt_id, date, vendor, category, amount, desc, payment, in_banking in withdrawals:
        total_wd += amount
        if in_banking == 'YES':
            in_banking_wd += 1
        else:
            not_in_banking_wd += 1
        marker = "⚠️ " if in_banking == 'NO' else "✅"
        print(f"  {marker} {receipt_id} | {date} | {vendor[:25]:25} | ${amount:>12,.2f} | Banking: {in_banking}")
        if desc:
            print(f"       Description: {desc[:70]}")
    
    print(f"\nTotal: {len(withdrawals)} receipts, ${total_wd:,.2f}")
    print(f"In banking: {in_banking_wd}/{len(withdrawals)} ({100*in_banking_wd/len(withdrawals) if withdrawals else 0:.1f}%)")
    print(f"NOT in banking: {not_in_banking_wd}/{len(withdrawals)} ({100*not_in_banking_wd/len(withdrawals) if withdrawals else 0:.1f}%)")
    
    # Check unmatched banking for these large amounts
    print("\n\n5. UNMATCHED BANKING - Looking for these amounts in banking")
    print("-" * 80)
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.credit_amount
        FROM banking_transactions bt
        LEFT JOIN banking_receipt_matching_ledger brml ON bt.transaction_id = brml.banking_transaction_id
        WHERE brml.banking_transaction_id IS NULL
          AND (bt.debit_amount > 1000 OR bt.credit_amount > 1000)
          AND (bt.description LIKE '%DEPOSIT%'
           OR bt.description LIKE '%WITHDRAWAL%'
           OR bt.description LIKE '%JOURNAL%'
           OR bt.description LIKE '%TRANSFER%')
        ORDER BY COALESCE(bt.debit_amount, bt.credit_amount) DESC
        LIMIT 50
    """)
    
    unmatched_banking = cur.fetchall()
    print(f"Found {len(unmatched_banking)} large unmatched banking transactions (>$1000)")
    
    deposits = []
    withdrawals_b = []
    journals_b = []
    transfers = []
    
    for tx_id, date, desc, debit, credit in unmatched_banking:
        amount = debit or credit
        tx_type = "DEBIT" if debit else "CREDIT"
        
        if "DEPOSIT" in desc.upper():
            deposits.append((tx_id, date, desc, amount, tx_type))
        elif "WITHDRAWAL" in desc.upper() or "WD" in desc.upper():
            withdrawals_b.append((tx_id, date, desc, amount, tx_type))
        elif "JOURNAL" in desc.upper():
            journals_b.append((tx_id, date, desc, amount, tx_type))
        elif "TRANSFER" in desc.upper():
            transfers.append((tx_id, date, desc, amount, tx_type))
    
    print(f"\nBreakdown of unmatched banking:")
    print(f"  Deposits: {len(deposits)}")
    for tx_id, date, desc, amount, tx_type in deposits[:10]:
        print(f"    {tx_id} | {date} | ${amount:>12,.2f} {tx_type} | {desc[:60]}")
    
    print(f"\n  Withdrawals: {len(withdrawals_b)}")
    for tx_id, date, desc, amount, tx_type in withdrawals_b[:10]:
        print(f"    {tx_id} | {date} | ${amount:>12,.2f} {tx_type} | {desc[:60]}")
    
    print(f"\n  Journal Entries: {len(journals_b)}")
    for tx_id, date, desc, amount, tx_type in journals_b[:10]:
        print(f"    {tx_id} | {date} | ${amount:>12,.2f} {tx_type} | {desc[:60]}")
    
    print(f"\n  Transfers: {len(transfers)}")
    for tx_id, date, desc, amount, tx_type in transfers[:10]:
        print(f"    {tx_id} | {date} | ${amount:>12,.2f} {tx_type} | {desc[:60]}")
    
    # Summary and recommendations
    print("\n" + "=" * 80)
    print("SUMMARY AND RECOMMENDATIONS")
    print("=" * 80)
    
    print(f"\n1. Monthly summaries: {len(summaries)} receipts, ${total_amount:,.2f}")
    print(f"   → {in_banking_count} in banking, {len(summaries)-in_banking_count} not in banking")
    print(f"   → RECOMMENDATION: Review if these should be journal entries instead")
    
    print(f"\n2. Journal entries in receipts: {len(journals)} receipts, ${total_journal:,.2f}")
    print(f"   → {in_banking_j} in banking, {len(journals)-in_banking_j} not in banking")
    print(f"   → RECOMMENDATION: These should likely be in journal table, not receipts")
    
    print(f"\n3. Large cash/cheque not in banking: {len(cash_missing)} receipts, ${total_cash:,.2f}")
    print(f"   → RECOMMENDATION: Verify these were actually paid, or match to banking deposits")
    
    print(f"\n4. Large withdrawals: {len(withdrawals)} receipts, ${total_wd:,.2f}")
    print(f"   → {in_banking_wd} in banking, {not_in_banking_wd} NOT in banking ⚠️")
    print(f"   → RECOMMENDATION: Withdrawals not in banking are likely bogus/duplicates")
    
    print(f"\n5. Unmatched banking: {len(unmatched_banking)} large transactions (>$1000)")
    print(f"   → {len(deposits)} deposits (likely monthly summaries)")
    print(f"   → {len(withdrawals_b)} withdrawals (should match to receipts)")
    print(f"   → {len(journals_b)} journal entries (accounting entries)")
    print(f"   → {len(transfers)} transfers (between accounts)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
