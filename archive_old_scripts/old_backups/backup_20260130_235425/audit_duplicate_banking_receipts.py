#!/usr/bin/env python3
"""
Audit for duplicate receipts - multiple receipts linked to same banking transaction
This should not happen - each banking transaction should have at most one receipt
"""
import psycopg2
import pandas as pd
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*100)
    print("DUPLICATE RECEIPTS AUDIT - Multiple Receipts Per Banking Transaction")
    print("="*100)
    
    # Find banking transactions with multiple receipts
    cur.execute("""
        SELECT 
            banking_transaction_id,
            COUNT(*) as receipt_count,
            ARRAY_AGG(receipt_id ORDER BY receipt_id) as receipt_ids,
            ARRAY_AGG(vendor_name ORDER BY receipt_id) as vendors,
            ARRAY_AGG(gross_amount ORDER BY receipt_id) as amounts,
            ARRAY_AGG(receipt_date ORDER BY receipt_id) as dates
        FROM receipts
        WHERE banking_transaction_id IS NOT NULL
        GROUP BY banking_transaction_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC, banking_transaction_id
    """)
    
    duplicates = cur.fetchall()
    
    if not duplicates:
        print("\n✅ No duplicate receipts found - all banking transactions have at most one receipt")
        cur.close()
        conn.close()
        return
    
    print(f"\n⚠️  Found {len(duplicates)} banking transactions with multiple receipts")
    print(f"Total affected receipts: {sum(d[1] for d in duplicates)}")
    
    # Get banking transaction details for context
    all_data = []
    
    for dup in duplicates:
        tx_id, count, receipt_ids, vendors, amounts, dates = dup
        
        # Get banking transaction details
        cur.execute("""
            SELECT 
                transaction_date,
                description,
                debit_amount,
                credit_amount,
                account_number
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (tx_id,))
        
        bank_info = cur.fetchone()
        if not bank_info:
            continue
        
        bank_date, bank_desc, bank_debit, bank_credit, bank_account = bank_info
        bank_amount = bank_debit if bank_debit else bank_credit
        
        # Account name
        account_name = "CIBC 0228362" if bank_account == '0228362' else "Scotia 903990106011"
        
        all_data.append({
            'tx_id': tx_id,
            'count': count,
            'bank_date': bank_date,
            'bank_desc': bank_desc,
            'bank_amount': bank_amount,
            'account': account_name,
            'receipt_ids': receipt_ids,
            'vendors': vendors,
            'amounts': amounts,
            'dates': dates
        })
    
    # Sort by count (most duplicates first) then by amount
    all_data.sort(key=lambda x: (-x['count'], -abs(float(x['bank_amount']))))
    
    print("\n" + "="*100)
    print("DETAILED DUPLICATE ANALYSIS")
    print("="*100)
    
    # Group by duplicate count
    by_count = {}
    for item in all_data:
        count = item['count']
        if count not in by_count:
            by_count[count] = []
        by_count[count].append(item)
    
    for count in sorted(by_count.keys(), reverse=True):
        items = by_count[count]
        print(f"\n{'='*100}")
        print(f"{count} RECEIPTS PER BANKING TRANSACTION ({len(items)} cases)")
        print(f"{'='*100}")
        
        for item in items[:20]:  # Show top 20 for each count level
            print(f"\nBanking TX #{item['tx_id']} | {item['account']}")
            print(f"  Date: {item['bank_date']} | Amount: ${item['bank_amount']:.2f}")
            print(f"  Description: {item['bank_desc']}")
            print(f"  {count} Receipts linked:")
            
            for i, (rec_id, vendor, amount, date) in enumerate(zip(
                item['receipt_ids'], item['vendors'], item['amounts'], item['dates']
            ), 1):
                print(f"    {i}. Receipt #{rec_id} | {date} | ${amount:.2f} | {vendor or 'NO VENDOR'}")
    
    # Summary by account
    print("\n" + "="*100)
    print("SUMMARY BY ACCOUNT")
    print("="*100)
    
    cibc_count = sum(1 for d in all_data if d['account'] == "CIBC 0228362")
    scotia_count = sum(1 for d in all_data if d['account'] == "Scotia 903990106011")
    
    print(f"\nCIBC 0228362: {cibc_count} banking transactions with duplicates")
    print(f"Scotia 903990106011: {scotia_count} banking transactions with duplicates")
    
    # Pattern analysis
    print("\n" + "="*100)
    print("DUPLICATE PATTERNS")
    print("="*100)
    
    # Check for same amount duplicates
    same_amount = []
    diff_amount = []
    
    for item in all_data:
        amounts = [float(a) for a in item['amounts']]
        bank_amt = float(item['bank_amount'])
        
        if len(set(amounts)) == 1:
            same_amount.append(item)
        else:
            diff_amount.append(item)
    
    print(f"\nSame amount duplicates: {len(same_amount)}")
    print(f"  (All receipts have identical amounts)")
    
    print(f"\nDifferent amount duplicates: {len(diff_amount)}")
    print(f"  (Receipts have different amounts - may be split transactions)")
    
    # Export to CSV for manual review
    csv_data = []
    for item in all_data:
        for i, (rec_id, vendor, amount, date) in enumerate(zip(
            item['receipt_ids'], item['vendors'], item['amounts'], item['dates']
        )):
            csv_data.append({
                'banking_tx_id': item['tx_id'],
                'bank_date': item['bank_date'],
                'bank_amount': item['bank_amount'],
                'bank_description': item['bank_desc'],
                'account': item['account'],
                'duplicate_count': item['count'],
                'receipt_id': rec_id,
                'receipt_vendor': vendor,
                'receipt_amount': amount,
                'receipt_date': date,
                'sequence': i + 1
            })
    
    df = pd.DataFrame(csv_data)
    output_file = f"l:/limo/reports/duplicate_banking_receipts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(output_file, index=False)
    
    print(f"\n{'='*100}")
    print(f"Detailed report saved to: {output_file}")
    print(f"{'='*100}")
    
    # Recommendations
    print("\n" + "="*100)
    print("RECOMMENDATIONS")
    print("="*100)
    print("""
1. SAME AMOUNT DUPLICATES: These are likely true duplicates that should be merged
   - Keep the oldest receipt (lowest receipt_id)
   - Delete the duplicate(s)
   
2. DIFFERENT AMOUNT DUPLICATES: Review these carefully
   - May be legitimate split transactions (one banking withdrawal → multiple expenses)
   - Check if amounts sum to banking amount
   - If legitimate splits, keep all but ensure they're marked as split_key group
   
3. NEXT STEPS:
   - Review the CSV export for detailed analysis
   - Create a cleanup script to:
     a) Merge true duplicates (same amount, same vendor)
     b) Properly mark legitimate splits
     c) Delete incorrect duplicates
    """)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
