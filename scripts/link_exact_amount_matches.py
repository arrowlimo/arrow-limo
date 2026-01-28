"""Link banking transactions to receipts with exact date and amount matches."""

import psycopg2
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true', help='Apply matches to database')
    args = parser.parse_args()
    
    conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***',
        host='localhost'
    )
    cur = conn.cursor()
    
    print('='*80)
    print('EXACT AMOUNT MATCHING - Banking to Receipts')
    print('='*80)
    print(f'Mode: {"WRITE" if args.write else "DRY RUN"}')
    print()
    
    # Find exact matches (date and amount within $0.01)
    print('Finding exact date + amount matches...')
    cur.execute('''
        SELECT 
            bt.transaction_id,
            r.receipt_id,
            bt.transaction_date,
            bt.debit_amount,
            COALESCE(bt.vendor_extracted, LEFT(bt.description, 30)) as bank_vendor,
            r.vendor_name as receipt_vendor
        FROM banking_transactions bt
        JOIN receipts r ON r.receipt_date = bt.transaction_date 
            AND ABS(r.gross_amount - bt.debit_amount) < 0.01
        WHERE bt.debit_amount > 0
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger bm
            WHERE bm.banking_transaction_id = bt.transaction_id
            AND bm.receipt_id = r.receipt_id
        )
        ORDER BY bt.debit_amount DESC
    ''')
    
    matches = cur.fetchall()
    print(f'Found {len(matches):,} exact matches')
    print()
    
    if len(matches) == 0:
        print('No new matches to process.')
        cur.close()
        conn.close()
        return
    
    # Show sample
    print('Sample matches (first 20):')
    print('-'*80)
    print(f'{"Date":<12s} {"Amount":>10s} {"Bank Vendor":<30s} {"Receipt Vendor":<30s}')
    print('-'*80)
    for i, (txn_id, rcpt_id, date, amount, bank_v, receipt_v) in enumerate(matches[:20]):
        print(f'{str(date):<12s} ${amount:>9,.2f} {(bank_v or "")[:30]:<30s} {(receipt_v or "")[:30]:<30s}')
    
    if len(matches) > 20:
        print(f'... and {len(matches)-20:,} more')
    print()
    
    if args.write:
        print(f'Creating {len(matches):,} links in banking_receipt_matching_ledger...')
        
        # Insert matches
        for txn_id, rcpt_id, date, amount, bank_v, receipt_v in matches:
            cur.execute('''
                INSERT INTO banking_receipt_matching_ledger (
                    banking_transaction_id,
                    receipt_id,
                    match_date,
                    match_type,
                    match_status,
                    match_confidence,
                    notes,
                    created_by
                ) VALUES (
                    %s, %s, CURRENT_DATE,
                    'exact_date_amount', 'matched', '95',
                    'Auto-linked: exact date and amount match',
                    'link_exact_amount_matches.py'
                )
                ON CONFLICT DO NOTHING
            ''', (txn_id, rcpt_id))
        
        conn.commit()
        print(f'✓ Created {len(matches):,} new links')
    else:
        print('DRY RUN - No changes made')
        print('Run with --write to apply matches')
    
    print()
    print('='*80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
