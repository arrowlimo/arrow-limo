#!/usr/bin/env python3
"""
Identify BOGUS QuickBooks entries that conflict with VERIFIED banking records
Rule: Banking records (Scotia + CIBC except 8032) are VERIFIED and LOCKED
      Any duplicate with different amount = QuickBooks is BOGUS
"""
import psycopg2
import pandas as pd
from datetime import datetime
import re

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def extract_cheque_number(text):
    """Extract cheque number from text"""
    if not text:
        return None
    
    patterns = [
        r'CHQ\s*#?\s*(\d+)',
        r'CHEQUE\s*#?\s*(\d+)',
        r'CHECK\s*#?\s*(\d+)',
        r'Cheque\s+(\d{6,})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*100)
    print("BOGUS QUICKBOOKS ENTRY IDENTIFICATION")
    print("VERIFIED BANKING RECORDS (Scotia + CIBC except 8032) = TRUTH")
    print("QuickBooks duplicates with different amounts = BOGUS")
    print("="*100)
    
    # Get all banking transactions with cheque numbers and their verification status
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            account_number,
            verified,
            locked,
            source_file
        FROM banking_transactions
        WHERE description ~* '(CHQ|CHEQUE|CHECK)\\s*#?\\s*\\d+'
        AND account_number IN ('0228362', '903990106011')  -- CIBC and Scotia only (excluding 8032)
        ORDER BY transaction_date
    """)
    
    banking_cheques = cur.fetchall()
    
    # Build verified banking cheque registry
    verified_cheques = {}  # cheque_num -> list of verified banking transactions
    
    for tx_id, date, desc, debit, credit, acct, verified, locked, source in banking_cheques:
        chq_num = extract_cheque_number(desc)
        if chq_num:
            if chq_num not in verified_cheques:
                verified_cheques[chq_num] = []
            
            amount = debit if debit else credit
            verified_cheques[chq_num].append({
                'tx_id': tx_id,
                'date': date,
                'amount': amount,
                'desc': desc,
                'account': acct,
                'verified': verified,
                'locked': locked,
                'source': 'BANKING_VERIFIED'
            })
    
    print(f"\nFound {len(verified_cheques)} unique cheque numbers in VERIFIED banking records")
    
    # Now check receipts for conflicts
    print(f"\n{'='*100}")
    print("CHECKING RECEIPTS FOR BOGUS QUICKBOOKS ENTRIES")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.description,
            r.source_reference,
            r.vendor_name,
            r.gross_amount,
            r.banking_transaction_id,
            r.source_system,
            r.created_from_banking,
            bt.description as bank_desc,
            bt.account_number
        FROM receipts r
        LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE (r.description ~* '(CHQ|CHEQUE|CHECK)\\s*#?\\s*\\d+'
            OR r.source_reference ~* 'CHQ')
        AND r.source_system IS NOT NULL
        ORDER BY r.receipt_date
    """)
    
    receipt_cheques = cur.fetchall()
    
    bogus_receipts = []
    conflicts = []
    
    for rec_id, date, desc, src_ref, vendor, amount, bank_tx, source_sys, from_banking, bank_desc, bank_acct in receipt_cheques:
        chq_num = extract_cheque_number(desc) or extract_cheque_number(src_ref)
        
        if chq_num and chq_num in verified_cheques:
            # This cheque number exists in verified banking
            banking_entries = verified_cheques[chq_num]
            
            # Check if this receipt conflicts with verified banking
            matches_banking = False
            if amount:  # Skip if receipt has no amount
                for bank_entry in banking_entries:
                    # Check if amounts match (within $0.10 for rounding)
                    bank_amt = float(bank_entry['amount']) if bank_entry['amount'] else 0
                    if abs(float(amount) - bank_amt) < 0.10:
                        matches_banking = True
                        break
            
            if not matches_banking:
                # BOGUS - QuickBooks entry doesn't match any verified banking entry
                banking_amounts = [float(b['amount']) for b in banking_entries]
                
                # Don't flag if it was created from banking (those are legitimate)
                if not from_banking:
                    bogus_receipts.append({
                        'receipt_id': rec_id,
                        'cheque_num': chq_num,
                        'receipt_date': date,
                        'receipt_amount': float(amount),
                        'vendor': vendor,
                        'source_system': source_sys,
                        'banking_amounts': banking_amounts,
                        'banking_tx_ids': [b['tx_id'] for b in banking_entries],
                        'reason': 'AMOUNT_MISMATCH_WITH_VERIFIED_BANKING'
                    })
                    
                    conflicts.append({
                        'cheque_num': chq_num,
                        'receipt': {
                            'id': rec_id,
                            'date': date,
                            'amount': float(amount),
                            'vendor': vendor,
                            'source': source_sys
                        },
                        'banking': banking_entries
                    })
    
    print(f"\n🚨 Found {len(bogus_receipts)} BOGUS QuickBooks receipt entries")
    print(f"   (Cheque numbers exist in verified banking but with DIFFERENT amounts)")
    
    if conflicts:
        print(f"\n{'='*100}")
        print("DETAILED CONFLICTS - QuickBooks vs Verified Banking")
        print(f"{'='*100}")
        
        # Group by cheque number
        by_cheque = {}
        for conflict in conflicts:
            chq = conflict['cheque_num']
            if chq not in by_cheque:
                by_cheque[chq] = {'receipts': [], 'banking': conflict['banking']}
            by_cheque[chq]['receipts'].append(conflict['receipt'])
        
        # Sort by cheque number
        sorted_cheques = sorted(by_cheque.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
        
        for chq_num, data in sorted_cheques[:50]:  # Show top 50
            print(f"\n🚨 CHEQUE #{chq_num}")
            
            print(f"  VERIFIED BANKING (TRUTH):")
            for bank in data['banking']:
                acct_name = "CIBC 0228362" if "0228362" in str(bank['account']) else "Scotia 903990106011"
                print(f"    ✓ TX #{bank['tx_id']} | {bank['date']} | ${bank['amount']:.2f} | {acct_name}")
                print(f"      {bank['desc'][:80]}")
            
            print(f"  BOGUS QuickBooks Receipts (DELETE THESE):")
            for receipt in data['receipts']:
                print(f"    ✗ Receipt #{receipt['id']} | {receipt['date']} | ${receipt['amount']:.2f}")
                print(f"      Vendor: {receipt['vendor'] or 'NO VENDOR'} | Source: {receipt['source']}")
    
    # Check for 2013 duplicates specifically
    print(f"\n{'='*100}")
    print("2013 CHEQUE NUMBER REUSE ANALYSIS")
    print(f"{'='*100}")
    
    reused_cheques = {}
    for chq_num, entries in verified_cheques.items():
        if len(entries) > 1:
            # Check if spans 2012 and 2013
            years = set(e['date'].year for e in entries)
            if 2012 in years and 2013 in years:
                reused_cheques[chq_num] = entries
    
    print(f"\nFound {len(reused_cheques)} cheque numbers reused between 2012 and 2013")
    print("These are LEGITIMATE - new cheque book started in 2013 with same numbers")
    
    if reused_cheques:
        print("\nSample reused cheques:")
        for chq_num, entries in list(reused_cheques.items())[:10]:
            print(f"\n  CHQ #{chq_num}:")
            for entry in entries:
                year = entry['date'].year
                print(f"    {year}: ${entry['amount']:.2f} - {entry['desc'][:60]}")
    
    # Export bogus receipts list
    if bogus_receipts:
        df = pd.DataFrame(bogus_receipts)
        output_file = f"l:/limo/reports/bogus_qb_receipts_to_delete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n{'='*100}")
        print(f"BOGUS RECEIPTS LIST exported to: {output_file}")
        print(f"{'='*100}")
    
    # Summary
    print(f"\n{'='*100}")
    print("SUMMARY")
    print(f"{'='*100}")
    print(f"\nVERIFIED BANKING RECORDS (TRUTH):")
    print(f"  Scotia + CIBC cheques: {len(banking_cheques)} transactions")
    print(f"  Unique cheque numbers: {len(verified_cheques)}")
    
    print(f"\nBOGUS QUICKBOOKS ENTRIES (TO DELETE):")
    print(f"  Receipt records: {len(bogus_receipts)}")
    
    print(f"\nCHEQUE NUMBER REUSE (2012→2013):")
    print(f"  Legitimate reuse: {len(reused_cheques)} cheque numbers")
    print(f"  (New cheque book started in 2013 with same numbering)")
    
    print(f"\n{'='*100}")
    print("ACTION REQUIRED")
    print(f"{'='*100}")
    
    if bogus_receipts:
        print(f"""
DELETE {len(bogus_receipts)} BOGUS QuickBooks receipt entries:

DELETE FROM receipts 
WHERE receipt_id IN ({', '.join(str(r['receipt_id']) for r in bogus_receipts[:5])}, ...);

These receipts have cheque numbers that exist in VERIFIED banking but with
DIFFERENT amounts, indicating QuickBooks import errors.

VERIFIED BANKING RECORDS REMAIN UNTOUCHED - they are the source of truth.
""")
    else:
        print("\n✅ NO BOGUS QuickBooks receipts found conflicting with verified banking")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
