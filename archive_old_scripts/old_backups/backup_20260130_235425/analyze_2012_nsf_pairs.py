"""
Analyze NSF transaction pairs in 2012 to verify proper signing and cancellation.
"""

import psycopg2
from datetime import datetime, timedelta

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print('='*70)
    print('2012 NSF TRANSACTION PAIR ANALYSIS')
    print('='*70)
    print()
    
    # Find all NSF-related transactions
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            category
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND (
            vendor_name ILIKE '%NSF%'
            OR vendor_name ILIKE '%BOUNCE%'
            OR vendor_name ILIKE '%REVERSAL%'
            OR vendor_name ILIKE '%CORRECTION%'
            OR vendor_name ILIKE '%CHARGE BACK%'
            OR description ILIKE '%NSF%'
            OR description ILIKE '%BOUNCE%'
            OR description ILIKE '%REVERSAL%'
        )
        ORDER BY receipt_date, gross_amount
    """)
    
    nsf_transactions = cur.fetchall()
    
    print(f'Found {len(nsf_transactions)} NSF-related transactions in 2012')
    print()
    
    if not nsf_transactions:
        print('No NSF transactions found.')
        cur.close()
        conn.close()
        return
    
    # Group by date and amount to find pairs
    from collections import defaultdict
    pairs = defaultdict(list)
    
    for txn in nsf_transactions:
        rec_id, date, vendor, amount, desc, category = txn
        # Group by date (within 7 days) and absolute amount
        key = (date, abs(amount))
        pairs[key].append(txn)
    
    print('NSF Transaction Pairs:')
    print('-'*70)
    
    total_positive = 0
    total_negative = 0
    paired_count = 0
    unpaired_count = 0
    
    for (date, abs_amt), txns in sorted(pairs.items()):
        if len(txns) == 2:
            # Check if they cancel out
            amounts = [t[3] for t in txns]
            if abs(sum(amounts)) < 0.01:
                paired_count += 1
                print(f'✓ PAIR on {date}: ${abs_amt:,.2f}')
                for txn in txns:
                    sign = '+' if txn[3] > 0 else '-'
                    print(f'    {sign} ${txn[3]:>10,.2f} | {txn[2][:40]}')
            else:
                print(f'⚠ INCOMPLETE PAIR on {date}: ${abs_amt:,.2f}')
                for txn in txns:
                    sign = '+' if txn[3] > 0 else '-'
                    print(f'    {sign} ${txn[3]:>10,.2f} | {txn[2][:40]}')
        else:
            unpaired_count += len(txns)
            print(f'⚠ UNPAIRED on {date}: ${abs_amt:,.2f} ({len(txns)} transactions)')
            for txn in txns:
                sign = '+' if txn[3] > 0 else '-'
                print(f'    {sign} ${txn[3]:>10,.2f} | {txn[2][:40]}')
        
        for txn in txns:
            if txn[3] > 0:
                total_positive += txn[3]
            else:
                total_negative += txn[3]
        print()
    
    print('-'*70)
    print('SUMMARY:')
    print(f'  Paired NSF events: {paired_count}')
    print(f'  Unpaired transactions: {unpaired_count}')
    print(f'  Total Positive (charges): ${total_positive:,.2f}')
    print(f'  Total Negative (reversals): ${total_negative:,.2f}')
    print(f'  Net Impact: ${total_positive + total_negative:,.2f}')
    print()
    
    if abs(total_positive + total_negative) < 0.01:
        print('✅ All NSF transactions cancel out perfectly!')
    elif abs(total_positive + total_negative) < 50:
        print('⚠️  Small net impact (likely acceptable)')
    else:
        print('❌ WARNING: Significant net impact from NSF transactions')
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
