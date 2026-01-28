#!/usr/bin/env python3
"""
Verify TRUE duplicates - receipts that share the same banking transaction.
This is the ONLY type of duplicate that inflates expenses.

LEGITIMATE scenarios (NOT duplicates):
- Recurring payments (same amount, different dates, each with own banking TX)
- NSF retries (original NSF + successful retry, each with own banking TX)
- Multiple card transactions on same date (each is a separate banking TX)
"""

import psycopg2
import os
from decimal import Decimal

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("TRUE DUPLICATE VERIFICATION")
    print("Only checking for receipts sharing the same banking transaction")
    print("=" * 80)
    print()
    
    # Find banking transactions with multiple receipts
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            COUNT(r.receipt_id) as receipt_count,
            ARRAY_AGG(r.receipt_id ORDER BY r.receipt_id) as receipt_ids,
            ARRAY_AGG(r.gross_amount ORDER BY r.receipt_id) as receipt_amounts,
            ARRAY_AGG(r.vendor_name ORDER BY r.receipt_id) as vendors,
            SUM(r.gross_amount) as total_receipts
        FROM banking_transactions bt
        INNER JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE r.exclude_from_reports = FALSE
        GROUP BY bt.transaction_id, bt.transaction_date, bt.description, bt.debit_amount
        HAVING COUNT(r.receipt_id) > 1
        ORDER BY SUM(r.gross_amount) DESC
    """)
    
    multiple_receipt_txs = cur.fetchall()
    
    print(f"Found {len(multiple_receipt_txs)} banking transactions with multiple receipts\n")
    
    total_inflation = Decimal('0')
    delete_candidates = []
    
    for tx_id, tx_date, tx_desc, tx_debit, rec_count, rec_ids, rec_amounts, vendors, rec_total in multiple_receipt_txs[:50]:
        
        # Calculate inflation (total receipts - banking debit)
        banking_amt = Decimal(str(tx_debit)) if tx_debit else Decimal('0')
        receipt_amt = Decimal(str(rec_total)) if rec_total else Decimal('0')
        inflation = receipt_amt - banking_amt
        total_inflation += inflation
        
        print(f"\n{'='*70}")
        print(f"Banking TX #{tx_id} | {tx_date}")
        print(f"Description: {tx_desc}")
        print(f"Banking debit: ${banking_amt:,.2f}")
        print(f"Receipt count: {rec_count}")
        print(f"Receipt IDs: {rec_ids}")
        print(f"Vendors: {vendors}")
        print(f"Receipt amounts: {[float(a) if a else 0 for a in rec_amounts]}")
        print(f"Total receipts: ${receipt_amt:,.2f}")
        print(f"INFLATION: ${inflation:,.2f}")
        
        # Determine if this is a legitimate split or a duplicate
        unique_amounts = set(rec_amounts)
        unique_vendors = set(vendors)
        
        if len(unique_amounts) == 1 and len(unique_vendors) == 1:
            # All receipts same amount/vendor - DEFINITE DUPLICATE
            print(f">>> TRUE DUPLICATE: {rec_count} identical receipts for 1 banking TX")
            print(f">>> RECOMMENDATION: Keep 1 receipt, delete {rec_count - 1} duplicates")
            
            # Add to delete candidates (keep first, delete rest)
            for rid in rec_ids[1:]:
                delete_candidates.append({
                    'receipt_id': rid,
                    'amount': float(rec_amounts[1]) if rec_amounts[1] else 0,
                    'vendor': vendors[1],
                    'date': tx_date,
                    'banking_tx': tx_id
                })
        
        elif len(unique_amounts) > 1:
            # Different amounts - could be legitimate split
            print(f">>> MIXED AMOUNTS: May be legitimate split transaction")
            print(f">>> NEEDS REVIEW: Verify if amounts sum to banking debit")
            
            # Check if amounts sum to banking debit
            amount_sum = sum(Decimal(str(a)) if a else Decimal('0') for a in rec_amounts)
            if abs(amount_sum - banking_amt) < Decimal('0.02'):
                print(f">>> LIKELY LEGITIMATE: Amounts sum to banking debit (${amount_sum:,.2f})")
            else:
                print(f">>> SUSPICIOUS: Amounts (${amount_sum:,.2f}) != banking (${banking_amt:,.2f})")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nBanking TXs with multiple receipts: {len(multiple_receipt_txs)}")
    print(f"Total inflation from duplicates (top 50): ${total_inflation:,.2f}")
    
    print(f"\nTRUE DUPLICATES IDENTIFIED: {len(delete_candidates)} receipts")
    if delete_candidates:
        delete_total = sum(Decimal(str(d['amount'])) for d in delete_candidates)
        print(f"Inflation from true duplicates: ${delete_total:,.2f}")
        
        print(f"\nTop 10 deletion candidates:")
        for dc in sorted(delete_candidates, key=lambda x: x['amount'], reverse=True)[:10]:
            print(f"  Receipt #{dc['receipt_id']}: ${dc['amount']:,.2f} | {dc['vendor']} | {dc['date']}")
    
    # Check for unlinked duplicates (same date/vendor/amount, no banking link)
    print("\n" + "=" * 80)
    print("UNLINKED DUPLICATES (no banking transaction)")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            gross_amount,
            COUNT(*) as dup_count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids,
            ARRAY_AGG(receipt_source ORDER BY receipt_id) as sources
        FROM receipts
        WHERE banking_transaction_id IS NULL
          AND exclude_from_reports = FALSE
          AND gross_amount IS NOT NULL
          AND gross_amount > 0
        GROUP BY receipt_date, vendor_name, gross_amount
        HAVING COUNT(*) > 1
        ORDER BY gross_amount DESC, receipt_date
        LIMIT 20
    """)
    
    unlinked_dupes = cur.fetchall()
    
    print(f"\nFound {cur.rowcount} sets of unlinked duplicates (showing top 20)\n")
    
    unlinked_inflation = Decimal('0')
    for date, vendor, amount, count, rec_ids, sources in unlinked_dupes:
        amt = Decimal(str(amount)) if amount else Decimal('0')
        inflation = amt * (count - 1)
        unlinked_inflation += inflation
        
        print(f"\n{date} | {vendor} | ${amt:,.2f} x {count}")
        print(f"  Receipt IDs: {rec_ids}")
        print(f"  Sources: {sources}")
        print(f"  Inflation: ${inflation:,.2f}")
    
    print(f"\nTotal inflation from unlinked duplicates (top 20): ${unlinked_inflation:,.2f}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("1. Review true duplicates (same banking TX, identical receipts)")
    print("2. Delete duplicate receipts keeping only 1 per banking transaction")
    print("3. Review mixed-amount cases for legitimate splits")
    print("4. Check unlinked duplicates against banking to find matches")

if __name__ == "__main__":
    main()
