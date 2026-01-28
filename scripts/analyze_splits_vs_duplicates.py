#!/usr/bin/env python3
"""
Analyze receipts with same banking_transaction_id.
Distinguish between:
  - LEGITIMATE SPLITS (marked with split_key/is_split_receipt)
  - IMPORT DUPLICATES (same vendor/amount, not marked as split)
"""

import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("BANKING TRANSACTION ONE-TO-MANY ANALYSIS")
    print("Checking for legitimate splits vs import duplicates")
    print("=" * 80)
    print()
    
    # Get banking TXs with multiple receipts
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            COUNT(r.receipt_id) as receipt_count,
            ARRAY_AGG(r.receipt_id ORDER BY r.receipt_id) as receipt_ids,
            ARRAY_AGG(r.gross_amount ORDER BY r.receipt_id) as amounts,
            ARRAY_AGG(r.vendor_name ORDER BY r.receipt_id) as vendors,
            ARRAY_AGG(r.is_split_receipt ORDER BY r.receipt_id) as is_splits,
            ARRAY_AGG(r.split_key ORDER BY r.receipt_id) as split_keys,
            ARRAY_AGG(r.expense_account ORDER BY r.receipt_id) as accounts
        FROM banking_transactions bt
        INNER JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE r.exclude_from_reports = FALSE
        GROUP BY bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount
        HAVING COUNT(r.receipt_id) > 1
        ORDER BY COUNT(r.receipt_id) DESC, bt.debit_amount DESC
        LIMIT 100
    """)
    
    multi_receipt_txs = cur.fetchall()
    
    print(f"Found {len(multi_receipt_txs)} banking TXs with multiple receipts (showing top 100)\n")
    
    legitimate_splits = []
    import_duplicates = []
    mixed_cases = []
    
    for tx_id, tx_date, tx_desc, tx_debit, rec_count, rec_ids, amounts, vendors, is_splits, split_keys, accounts in multi_receipt_txs:
        
        banking_amt = Decimal(str(tx_debit)) if tx_debit else Decimal('0')
        total_receipts = sum(Decimal(str(a)) if a else Decimal('0') for a in amounts)
        
        # Check if marked as split
        has_split_flag = any(is_splits)
        has_split_key = any(split_keys)
        
        # Check if amounts sum to banking (within 2 cents)
        amounts_match = abs(total_receipts - banking_amt) < Decimal('0.02')
        
        # Check if different vendors or accounts
        unique_vendors = len(set(vendors))
        unique_accounts = len(set(a for a in accounts if a))
        
        # Classify
        if has_split_flag or has_split_key:
            # Marked as split
            legitimate_splits.append({
                'tx_id': tx_id,
                'date': tx_date,
                'banking_amt': float(banking_amt),
                'receipt_count': rec_count,
                'total_receipts': float(total_receipts),
                'reason': 'Has split flag/key'
            })
            category = "✅ LEGITIMATE SPLIT (flagged)"
        
        elif amounts_match and (unique_vendors > 1 or unique_accounts > 1):
            # Amounts match and different categories - likely legitimate unflagged split
            legitimate_splits.append({
                'tx_id': tx_id,
                'date': tx_date,
                'banking_amt': float(banking_amt),
                'receipt_count': rec_count,
                'total_receipts': float(total_receipts),
                'reason': 'Amounts sum, different categories'
            })
            category = "✅ LEGITIMATE SPLIT (unflagged)"
        
        elif unique_vendors == 1 and unique_accounts <= 1 and not amounts_match:
            # Same vendor, same/no account, amounts don't match - IMPORT DUPLICATE
            import_duplicates.append({
                'tx_id': tx_id,
                'date': tx_date,
                'banking_amt': float(banking_amt),
                'receipt_ids': rec_ids,
                'amounts': [float(a) if a else 0 for a in amounts],
                'vendor': vendors[0],
                'inflation': float(total_receipts - banking_amt)
            })
            category = "❌ IMPORT DUPLICATE"
        
        else:
            # Mixed/unclear
            mixed_cases.append({
                'tx_id': tx_id,
                'date': tx_date,
                'banking_amt': float(banking_amt),
                'receipt_count': rec_count,
                'total_receipts': float(total_receipts),
                'unique_vendors': unique_vendors,
                'amounts_match': amounts_match
            })
            category = "⚠️  NEEDS REVIEW"
        
        # Print first 30 for inspection
        if len(legitimate_splits) + len(import_duplicates) + len(mixed_cases) <= 30:
            print(f"\nTX #{tx_id} | {tx_date} | {category}")
            print(f"  Banking: ${banking_amt:,.2f} | Receipts: {rec_count} x ${total_receipts:,.2f}")
            print(f"  Receipt IDs: {rec_ids}")
            print(f"  Amounts: {[float(a) if a else 0 for a in amounts]}")
            print(f"  Vendors: {vendors}")
            print(f"  Accounts: {accounts}")
            print(f"  Split flags: {is_splits} | Keys: {split_keys}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\n✅ LEGITIMATE SPLITS: {len(legitimate_splits)}")
    if legitimate_splits[:5]:
        for ls in legitimate_splits[:5]:
            print(f"   TX #{ls['tx_id']}: ${ls['banking_amt']:,.2f} → {ls['receipt_count']} receipts (${ls['total_receipts']:,.2f})")
    
    print(f"\n❌ IMPORT DUPLICATES: {len(import_duplicates)}")
    total_dup_inflation = sum(d['inflation'] for d in import_duplicates)
    print(f"   Total inflation: ${total_dup_inflation:,.2f}")
    
    if import_duplicates[:10]:
        print("\n   Top 10 by inflation:")
        for d in sorted(import_duplicates, key=lambda x: abs(x['inflation']), reverse=True)[:10]:
            print(f"   TX #{d['tx_id']}: {d['vendor']}")
            print(f"      Banking ${d['banking_amt']:,.2f} → Receipts {d['receipt_ids']}")
            print(f"      Amounts: {d['amounts']} | Inflation: ${d['inflation']:,.2f}")
    
    print(f"\n⚠️  MIXED/NEEDS REVIEW: {len(mixed_cases)}")
    if mixed_cases[:5]:
        for mc in mixed_cases[:5]:
            print(f"   TX #{mc['tx_id']}: {mc['receipt_count']} receipts, {mc['unique_vendors']} vendors, sum={'match' if mc['amounts_match'] else 'mismatch'}")
    
    # Check unlinked receipts (legitimate non-banking sources)
    print("\n" + "=" * 80)
    print("UNLINKED RECEIPTS (Non-Banking Sources)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            receipt_source,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE banking_transaction_id IS NULL
          AND exclude_from_reports = FALSE
        GROUP BY receipt_source
        ORDER BY SUM(gross_amount) DESC
    """)
    
    print("\nReceipts without banking_transaction_id:")
    unlinked_total = Decimal('0')
    for src, cnt, total in cur.fetchall():
        amt = Decimal(str(total)) if total else Decimal('0')
        unlinked_total += amt
        print(f"  {src if src else 'NULL':<30} {cnt:>5,} receipts  ${amt:>12,.2f}")
    
    print(f"\n  TOTAL UNLINKED: ${unlinked_total:,.2f}")
    
    print("\n" + "=" * 80)
    print("LEGITIMATE NON-BANKING SOURCES:")
    print("  - SQUARE payments (merchant deposits to bank, but individual card TXs not in banking)")
    print("  - CASH reimbursements (no banking trail)")
    print("  - LOANS from Karen Richard (personal, not banking)")
    print("  - TRADE/BARTER (no cash exchange)")
    print("  - DONATIONS RECEIVED (charitable, may not hit bank)")
    print("  - CALCULATED_FROM_FINANCING (depreciation, not a banking TX)")
    print("  - EMAIL_IMPORT (invoices/bills, not yet paid)")
    print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
