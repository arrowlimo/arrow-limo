#!/usr/bin/env python3
"""
Verify NSF pattern: Deduction → Reversal (deposit back) → NSF Fee
NSF pairs = $0 net (not income/expense, they cancel out)
Voided checks (not in banking) = $0 (never issued)
"""
import psycopg2
from datetime import timedelta

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
    
    print("="*100)
    print("NSF PATTERN VERIFICATION")
    print("Expected: Deduction (DEBIT) → Reversal (CREDIT) → NSF Fee (DEBIT)")
    print("NSF pairs net to $0 (not income/expense)")
    print("="*100)
    
    # Get all NSF-marked receipts
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount,
               description, banking_transaction_id, source_reference
        FROM receipts
        WHERE is_nsf = TRUE
        ORDER BY receipt_date
    """)
    
    nsf_receipts = cur.fetchall()
    
    print(f"\nFound {len(nsf_receipts)} receipts marked as NSF")
    print(f"\n{'='*100}")
    print("CHECKING NSF PATTERN FOR EACH RECEIPT")
    print(f"{'='*100}")
    
    nsf_with_reversal = []
    nsf_without_reversal = []
    nsf_fees = []
    
    for rec_id, date, vendor, amount, desc, bank_tx_id, src_ref in nsf_receipts:
        print(f"\n🚨 Receipt #{rec_id} | {date} | ${amount:,.2f} | {vendor or 'NO VENDOR'}")
        print(f"   Description: {desc or 'None'}")
        print(f"   Banking TX: {bank_tx_id}")
        
        if bank_tx_id:
            # Get the banking transaction
            cur.execute("""
                SELECT transaction_id, transaction_date, description,
                       debit_amount, credit_amount, account_number
                FROM banking_transactions
                WHERE transaction_id = %s
            """, (bank_tx_id,))
            
            tx = cur.fetchone()
            if tx:
                tx_id, tx_date, tx_desc, debit, credit, acct = tx
                tx_amount = debit if debit else credit
                tx_type = "DEBIT" if debit else "CREDIT"
                
                print(f"   Banking: TX #{tx_id} | {tx_date} | ${tx_amount:,.2f} {tx_type}")
                print(f"   Banking desc: {tx_desc[:80]}")
                
                # Look for reversal within 7 days
                search_start = tx_date
                search_end = tx_date + timedelta(days=7)
                
                cur.execute("""
                    SELECT transaction_id, transaction_date, description,
                           debit_amount, credit_amount
                    FROM banking_transactions
                    WHERE account_number = %s
                    AND transaction_date BETWEEN %s AND %s
                    AND (
                        (debit_amount = %s AND %s IS NOT NULL) OR
                        (credit_amount = %s AND %s IS NOT NULL)
                    )
                    AND description ILIKE '%%NSF%%'
                    ORDER BY transaction_date
                """, (acct, search_start, search_end, tx_amount, debit, tx_amount, credit))
                
                reversals = cur.fetchall()
                
                if reversals:
                    print(f"   ✓ FOUND REVERSAL(S):")
                    for rev_id, rev_date, rev_desc, rev_debit, rev_credit in reversals:
                        rev_amount = rev_debit if rev_debit else rev_credit
                        rev_type = "DEBIT" if rev_debit else "CREDIT"
                        print(f"     TX #{rev_id} | {rev_date} | ${rev_amount:,.2f} {rev_type}")
                        print(f"     {rev_desc[:80]}")
                    
                    # Look for NSF fee
                    cur.execute("""
                        SELECT transaction_id, transaction_date, description,
                               debit_amount
                        FROM banking_transactions
                        WHERE account_number = %s
                        AND transaction_date BETWEEN %s AND %s
                        AND (description ILIKE '%%NSF FEE%%' OR description ILIKE '%%NSF CHARGE%%'
                             OR description ILIKE '%%RETURNED ITEM%%')
                        ORDER BY transaction_date
                    """, (acct, search_start, search_end))
                    
                    fees = cur.fetchall()
                    if fees:
                        print(f"   💰 NSF FEE(S):")
                        for fee_id, fee_date, fee_desc, fee_amount in fees:
                            print(f"     TX #{fee_id} | {fee_date} | ${fee_amount:,.2f} DEBIT")
                            print(f"     {fee_desc[:80]}")
                            nsf_fees.append({
                                'receipt_id': rec_id,
                                'fee_tx_id': fee_id,
                                'fee_amount': float(fee_amount) if fee_amount else 0,
                                'fee_date': fee_date
                            })
                    
                    nsf_with_reversal.append({
                        'receipt_id': rec_id,
                        'amount': float(amount) if amount else 0,
                        'vendor': vendor,
                        'date': date,
                        'reversals': len(reversals)
                    })
                    print(f"   ✅ NET EFFECT: $0 (deduction + reversal cancel out)")
                else:
                    print(f"   ❌ NO REVERSAL FOUND - This IS a real expense")
                    nsf_without_reversal.append({
                        'receipt_id': rec_id,
                        'amount': float(amount) if amount else 0,
                        'vendor': vendor,
                        'date': date
                    })
        else:
            print(f"   ⚠️  NO BANKING TRANSACTION - Voided check?")
            nsf_without_reversal.append({
                'receipt_id': rec_id,
                'amount': float(amount) if amount else 0,
                'vendor': vendor,
                'date': date
            })
    
    # Now check for VOIDED checks (in receipts but not in banking)
    print(f"\n{'='*100}")
    print("VOIDED CHECKS - In receipts but NOT in banking")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
               r.description, r.source_reference, r.banking_transaction_id,
               r.is_voided
        FROM receipts r
        WHERE (r.description ILIKE '%CHQ%' OR r.description ILIKE '%CHEQUE%' OR r.source_reference ILIKE '%CHQ%')
        AND r.banking_transaction_id IS NULL
        AND r.source_system NOT IN ('verified_banking')
        AND r.gross_amount > 0
        ORDER BY r.receipt_date
    """)
    
    voided_checks = cur.fetchall()
    
    print(f"\nFound {len(voided_checks)} checks in receipts but NOT in banking")
    
    voided_list = []
    for rec_id, date, vendor, amount, desc, src_ref, bank_tx, is_void in voided_checks[:50]:  # Show first 50
        void_flag = "🚫VOID" if is_void else ""
        print(f"\n  Receipt #{rec_id} | {date} | ${amount:,.2f} | {vendor or 'NO VENDOR'} {void_flag}")
        print(f"  Desc: {desc[:80] if desc else 'None'}")
        print(f"  Ref: {src_ref}")
        print(f"  ⚠️  NOT IN BANKING - Never cleared = NOT an expense")
        
        voided_list.append({
            'receipt_id': rec_id,
            'amount': float(amount) if amount else 0,
            'vendor': vendor,
            'date': date,
            'is_voided': is_void
        })
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY - TRANSACTIONS THAT SHOULD BE $0 FOR REPORTING")
    print(f"{'='*100}")
    
    total_nsf_pairs = sum(item['amount'] for item in nsf_with_reversal)
    total_nsf_fees = sum(item['fee_amount'] for item in nsf_fees)
    total_voided = sum(item['amount'] for item in voided_list)
    
    print(f"\nNSF PAIRS (Deduction + Reversal = $0 net):")
    print(f"  Count: {len(nsf_with_reversal)} receipts")
    print(f"  Total amount: ${total_nsf_pairs:,.2f} (but NET = $0)")
    print(f"  → Should NOT count as expense (they cancelled out)")
    
    print(f"\nNSF FEES (Actual bank charges):")
    print(f"  Count: {len(nsf_fees)} fees")
    print(f"  Total: ${total_nsf_fees:,.2f}")
    print(f"  → These ARE real expenses")
    
    print(f"\nNSF WITHOUT REVERSAL (Real expenses):")
    print(f"  Count: {len(nsf_without_reversal)} receipts")
    total_real_nsf = sum(item['amount'] for item in nsf_without_reversal)
    print(f"  Total: ${total_real_nsf:,.2f}")
    print(f"  → These ARE real expenses")
    
    print(f"\nVOIDED CHECKS (Not in banking):")
    print(f"  Count: {len(voided_list)} receipts")
    print(f"  Total amount: ${total_voided:,.2f}")
    print(f"  → Should NOT count as expense (never cleared)")
    
    print(f"\n{'='*100}")
    print("RECOMMENDED ACTIONS")
    print(f"{'='*100}")
    
    print(f"""
1. NSF PAIRS WITH REVERSAL ({len(nsf_with_reversal)} receipts):
   - Mark as gross_amount = 0 (they net to $0)
   - OR add exclude_from_reports = TRUE flag
   - Keep original amount in a separate column for audit trail
   
2. NSF FEES ({len(nsf_fees)} fees):
   - Keep as-is (real bank charges)
   - Ensure vendor = "BANK NSF FEE" or similar
   
3. VOIDED CHECKS ({len(voided_list)} receipts):
   - Set gross_amount = 0 (never cleared)
   - OR set is_voided = TRUE flag
   - OR delete if confirmed voided

QUESTION: Should we mark NSF pairs and voided checks as $0,
or add an exclude_from_reports flag to avoid confusion?
""")
    
    # Export lists for review
    import pandas as pd
    from datetime import datetime
    
    if nsf_with_reversal:
        df_nsf = pd.DataFrame(nsf_with_reversal)
        nsf_file = f"l:/limo/reports/nsf_pairs_to_zero_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_nsf.to_csv(nsf_file, index=False)
        print(f"\n✓ NSF pairs exported to: {nsf_file}")
    
    if voided_list:
        df_void = pd.DataFrame(voided_list)
        void_file = f"l:/limo/reports/voided_checks_to_zero_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_void.to_csv(void_file, index=False)
        print(f"✓ Voided checks exported to: {void_file}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
