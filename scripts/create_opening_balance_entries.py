#!/usr/bin/env python3
"""
Create opening balance entries for 2012 accounting reconciliation.
"""
import psycopg2
from datetime import datetime, date

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*70)
    print("OPENING BALANCE ANALYSIS FOR 2012")
    print("="*70)
    
    # Find first transaction and opening balance for each account
    print("\n1. First transactions by account:\n")
    
    cur.execute("""
        SELECT 
            account_number,
            MIN(transaction_date) as first_date,
            (SELECT balance 
             FROM banking_transactions bt2 
             WHERE bt2.account_number = bt.account_number 
             ORDER BY transaction_date, transaction_id 
             LIMIT 1) as opening_balance,
            (SELECT description
             FROM banking_transactions bt2 
             WHERE bt2.account_number = bt.account_number 
             ORDER BY transaction_date, transaction_id 
             LIMIT 1) as first_description
        FROM banking_transactions bt
        WHERE account_number IN ('0228362', '903990106011', '1615')
        GROUP BY account_number
        ORDER BY first_date
    """)
    
    accounts = cur.fetchall()
    
    print(f"{'Account':<20} {'First Date':<12} {'Opening Balance':>15} {'Description'}")
    print("-" * 80)
    
    opening_entries = []
    for acct, first_date, opening_bal, desc in accounts:
        print(f"{acct:<20} {first_date} ${opening_bal or 0:>13,.2f} {desc or 'N/A'}")
        
        if opening_bal and opening_bal != 0:
            # Determine bank_id
            bank_id = None
            if acct == '0228362':
                bank_id = 1
                bank_name = 'CIBC 0228362'
            elif acct == '903990106011':
                bank_id = 2
                bank_name = 'Scotia 903990106011'
            elif acct == '1615':
                bank_id = 4
                bank_name = 'CIBC 1615'
            
            # Set opening date to Jan 1, 2012 (or first transaction date)
            opening_date = date(2012, 1, 1) if first_date >= date(2012, 1, 1) else first_date
            
            opening_entries.append({
                'account': acct,
                'bank_name': bank_name,
                'bank_id': bank_id,
                'date': opening_date,
                'balance': opening_bal,
                'description': f'Opening Balance - {bank_name} as of {opening_date}'
            })
    
    if not opening_entries:
        print("\n✅ No opening balances needed - all accounts start at zero")
        return
    
    print(f"\n{'='*70}")
    print("OPENING BALANCE ENTRIES TO CREATE")
    print(f"{'='*70}\n")
    
    for entry in opening_entries:
        print(f"Account: {entry['bank_name']}")
        print(f"Date: {entry['date']}")
        print(f"Amount: ${entry['balance']:,.2f}")
        print(f"Description: {entry['description']}\n")
    
    print(f"{'='*70}")
    response = input(f"\nCreate {len(opening_entries)} opening balance entries? (yes/no): ")
    
    if response.strip().lower() != 'yes':
        print("❌ Cancelled")
        return
    
    # Create opening balance receipts
    print("\n📝 Creating opening balance entries...")
    
    for entry in opening_entries:
        # Insert into receipts table
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                revenue,
                gst_amount,
                net_amount,
                mapped_bank_account_id,
                source_system,
                category,
                business_personal,
                is_verified_banking,
                verified_source
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING receipt_id
        """, (
            entry['date'],
            'Opening Balance',
            entry['description'],
            None,  # gross_amount (this is revenue, not expense)
            entry['balance'],  # revenue
            0,  # no GST on opening balance
            entry['balance'],  # net_amount
            entry['bank_id'],
            'OPENING_BALANCE',
            'Opening Balance',
            'Business',
            True,  # is_verified_banking
            f"Opening Balance Entry - {entry['date']}"
        ))
        
        receipt_id = cur.fetchone()[0]
        print(f"✅ Created receipt {receipt_id} for {entry['bank_name']}: ${entry['balance']:,.2f}")
    
    conn.commit()
    
    print(f"\n{'='*70}")
    print("✅ OPENING BALANCE ENTRIES CREATED")
    print(f"{'='*70}")
    print(f"Created {len(opening_entries)} opening balance entries")
    print("\nThese entries establish the starting equity position for accounting.")
    print("They represent the cash/bank balances at the beginning of 2012.")
    
    # Show new totals
    cur.execute("SELECT COUNT(*) FROM receipts")
    total = cur.fetchone()[0]
    print(f"\nTotal receipts: {total:,}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
