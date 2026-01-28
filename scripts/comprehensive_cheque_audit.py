#!/usr/bin/env python3
"""
Comprehensive cheque audit - check all sources for duplicate cheque numbers
"""
import psycopg2
import pandas as pd
from datetime import datetime
import re

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def extract_cheque_number(text):
    """Extract cheque number from text"""
    if not text:
        return None
    
    # Patterns: CHQ 123, CHEQUE 123, CHECK 123, Cheque 000000123456
    patterns = [
        r'CHQ\s*#?\s*(\d+)',
        r'CHEQUE\s*#?\s*(\d+)',
        r'CHECK\s*#?\s*(\d+)',
        r'Cheque\s+(\d{6,})',  # Long cheque numbers
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
    print("COMPREHENSIVE CHEQUE NUMBER AUDIT")
    print("="*100)
    
    # Method 1: Check banking_transactions.check_number column
    print("\n" + "="*100)
    print("METHOD 1: banking_transactions.check_number column")
    print("="*100)
    
    cur.execute("""
        SELECT check_number, COUNT(*) as cnt
        FROM banking_transactions
        WHERE check_number IS NOT NULL AND check_number != ''
        GROUP BY check_number
        ORDER BY COUNT(*) DESC, check_number
        LIMIT 20
    """)
    
    results = cur.fetchall()
    print(f"\nTop 20 most common check numbers (if any):")
    for chq, cnt in results:
        print(f"  {chq}: {cnt} transactions")
    
    # Method 2: Extract from banking descriptions
    print(f"\n{'='*100}")
    print("METHOD 2: Extract cheque numbers from banking_transactions.description")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT 
            transaction_id,
            description,
            debit_amount,
            credit_amount,
            transaction_date,
            account_number
        FROM banking_transactions
        WHERE description ~* '(CHQ|CHEQUE|CHECK)\\s*#?\\s*\\d+'
        ORDER BY transaction_date
    """)
    
    banking_with_cheques = cur.fetchall()
    print(f"\nFound {len(banking_with_cheques)} banking transactions with cheque references in description")
    
    # Extract and group
    cheque_data = {}
    for tx_id, desc, debit, credit, date, acct in banking_with_cheques:
        chq_num = extract_cheque_number(desc)
        if chq_num:
            if chq_num not in cheque_data:
                cheque_data[chq_num] = []
            
            amount = debit if debit else credit
            cheque_data[chq_num].append({
                'tx_id': tx_id,
                'date': date,
                'amount': amount,
                'desc': desc,
                'account': acct
            })
    
    # Find duplicates with different amounts
    duplicates = {}
    for chq_num, transactions in cheque_data.items():
        if len(transactions) > 1:
            amounts = set(t['amount'] for t in transactions)
            if len(amounts) > 1:  # Different amounts = SUSPICIOUS
                duplicates[chq_num] = transactions
    
    print(f"\n🚨 Found {len(duplicates)} cheque numbers with MULTIPLE transactions and DIFFERENT amounts:")
    
    if duplicates:
        # Sort by cheque number for display
        sorted_cheques = sorted(duplicates.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)
        
        for chq_num, transactions in sorted_cheques[:50]:  # Show top 50
            print(f"\nCHEQUE #{chq_num} - {len(transactions)} transactions:")
            amounts = [t['amount'] for t in transactions]
            print(f"  Amounts: {amounts}")
            
            for t in transactions:
                account_name = "CIBC 0228362" if "0228362" in str(t['account']) else "Scotia 903990106011"
                print(f"  • TX #{t['tx_id']} | {t['date']} | ${t['amount']:.2f} | {account_name}")
                print(f"    {t['desc'][:80]}")
    
    # Method 3: Check receipts
    print(f"\n{'='*100}")
    print("METHOD 3: Extract cheque numbers from receipts")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT 
            receipt_id,
            description,
            source_reference,
            vendor_name,
            gross_amount,
            receipt_date,
            payment_method,
            banking_transaction_id
        FROM receipts
        WHERE (description ~* '(CHQ|CHEQUE|CHECK)\\s*#?\\s*\\d+'
            OR payment_method = 'CHEQUE'
            OR source_reference ~* 'CHQ')
        ORDER BY receipt_date
    """)
    
    receipt_with_cheques = cur.fetchall()
    print(f"\nFound {len(receipt_with_cheques)} receipts with cheque references")
    
    # Extract and group receipts
    receipt_cheque_data = {}
    for rec_id, desc, src_ref, vendor, amount, date, pay_method, bank_tx in receipt_with_cheques:
        # Try to extract from description first, then source_reference
        chq_num = extract_cheque_number(desc) or extract_cheque_number(src_ref)
        
        if chq_num:
            if chq_num not in receipt_cheque_data:
                receipt_cheque_data[chq_num] = []
            
            receipt_cheque_data[chq_num].append({
                'receipt_id': rec_id,
                'date': date,
                'amount': amount,
                'vendor': vendor,
                'desc': desc,
                'bank_tx': bank_tx
            })
    
    # Find receipt duplicates with different amounts
    receipt_duplicates = {}
    for chq_num, receipts in receipt_cheque_data.items():
        if len(receipts) > 1:
            amounts = set(float(r['amount']) for r in receipts if r['amount'])
            if len(amounts) > 1:  # Different amounts = SUSPICIOUS
                receipt_duplicates[chq_num] = receipts
    
    print(f"\n🚨 Found {len(receipt_duplicates)} cheque numbers in receipts with DIFFERENT amounts:")
    
    if receipt_duplicates:
        sorted_receipt_cheques = sorted(receipt_duplicates.items(), 
                                       key=lambda x: int(x[0]) if x[0].isdigit() else 0)
        
        for chq_num, receipts in sorted_receipt_cheques[:50]:
            print(f"\nCHEQUE #{chq_num} - {len(receipts)} receipts:")
            amounts = [float(r['amount']) for r in receipts if r['amount']]
            print(f"  Amounts: {amounts}")
            
            for r in receipts:
                bank_link = f"→ Bank TX #{r['bank_tx']}" if r['bank_tx'] else "NO BANK LINK"
                print(f"  • Receipt #{r['receipt_id']} | {r['date']} | ${r['amount']:.2f} | {r['vendor'] or 'NO VENDOR'}")
                print(f"    {bank_link} | {r['desc'][:70] if r['desc'] else 'NO DESC'}")
    
    # Export combined report
    export_data = []
    
    # Add banking duplicates
    for chq_num, transactions in duplicates.items():
        for t in transactions:
            export_data.append({
                'cheque_number': chq_num,
                'source': 'BANKING',
                'id': t['tx_id'],
                'date': t['date'],
                'amount': t['amount'],
                'description': t['desc'],
                'account': t['account'],
                'issue': 'DUPLICATE_DIFFERENT_AMOUNT'
            })
    
    # Add receipt duplicates
    for chq_num, receipts in receipt_duplicates.items():
        for r in receipts:
            export_data.append({
                'cheque_number': chq_num,
                'source': 'RECEIPTS',
                'id': r['receipt_id'],
                'date': r['date'],
                'amount': r['amount'],
                'description': r['desc'],
                'vendor': r['vendor'],
                'issue': 'DUPLICATE_DIFFERENT_AMOUNT'
            })
    
    if export_data:
        df = pd.DataFrame(export_data)
        output_file = f"l:/limo/reports/cheque_duplicates_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n{'='*100}")
        print(f"Detailed report exported to: {output_file}")
        print(f"{'='*100}")
    
    # Summary
    print(f"\n{'='*100}")
    print("AUDIT SUMMARY")
    print(f"{'='*100}")
    print(f"\nBANKING TRANSACTIONS:")
    print(f"  Total with cheque references: {len(banking_with_cheques)}")
    print(f"  Unique cheque numbers: {len(cheque_data)}")
    print(f"  🚨 DUPLICATES with different amounts: {len(duplicates)}")
    
    print(f"\nRECEIPTS:")
    print(f"  Total with cheque references: {len(receipt_with_cheques)}")
    print(f"  Unique cheque numbers: {len(receipt_cheque_data)}")
    print(f"  🚨 DUPLICATES with different amounts: {len(receipt_duplicates)}")
    
    print(f"\n{'='*100}")
    print("RECOMMENDATIONS")
    print(f"{'='*100}")
    
    total_issues = len(duplicates) + len(receipt_duplicates)
    
    if total_issues > 0:
        print(f"""
⚠️  FOUND {total_issues} CHEQUE NUMBERS WITH MULTIPLE ENTRIES AND DIFFERENT AMOUNTS

These are likely QuickBooks import errors where:
1. Same cheque number was used multiple times (error in QB)
2. Import duplicated the transaction with wrong amount
3. Manual entry created duplicate with different amount

RECOMMENDED ACTIONS:
1. Review the exported CSV file
2. For each duplicate cheque number:
   - Verify against physical cheque or bank statement
   - Keep the correct transaction (matching bank statement)
   - Delete or flag the bogus entry
   
3. Common patterns to look for:
   - One transaction matches vendor/date perfectly = keep that one
   - One is from QB import, one from manual entry = verify which is correct
   - Multiple QB imports = keep first one that matches bank
""")
    else:
        print("\n✅ NO DUPLICATE CHEQUES WITH DIFFERENT AMOUNTS FOUND")
        print("   Cheque number integrity is good!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
