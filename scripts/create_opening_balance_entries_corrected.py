#!/usr/bin/env python3
"""
Create opening balance entries for 2012 accounting reconciliation.
CORRECTED VERSION: Calculates opening balance as (first_balance - credit + debit)
"""
import psycopg2
from datetime import datetime, date

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = '***REMOVED***'

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*70)
    print("OPENING BALANCE ANALYSIS FOR 2012")
    print("="*70)
    
    # Get first transaction for each account and calculate opening balance
    print("\n1. First transactions by account:\n")
    
    cur.execute("""
        SELECT 
            account_number,
            transaction_date,
            balance,
            debit_amount,
            credit_amount,
            description,
            bank_id
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY account_number ORDER BY transaction_date, transaction_id) as rn
            FROM banking_transactions
            WHERE account_number IN ('0228362', '903990106011', '7461615')
        ) sub
        WHERE rn = 1
        ORDER BY transaction_date
    """)
    
    first_trans = cur.fetchall()
    
    print(f"{'Account':<20} {'First Date':<12} {'Balance':>12} {'Debit':>12} {'Credit':>12} {'Opening':>12}")
    print("-" * 90)
    
    opening_entries = []
    for acct, trans_date, balance, debit, credit, desc, bank_id in first_trans:
        # Calculate opening balance: balance after - credit + debit = balance before
        opening_bal = (balance or 0) - (credit or 0) + (debit or 0)
        
        print(f"{acct:<20} {trans_date} ${balance or 0:>10,.2f} ${debit or 0:>10,.2f} ${credit or 0:>10,.2f} ${opening_bal:>10,.2f}")
        
        if opening_bal != 0:
            # Determine bank name
            if acct == '0228362':
                bank_name = 'CIBC 0228362'
            elif acct == '903990106011':
                bank_name = 'Scotia 903990106011'
            elif acct == '7461615':
                bank_name = 'CIBC 1615'
            else:
                bank_name = f'Account {acct}'
            
            # Set opening date to Jan 1, 2012 or earlier if first trans is before that
            opening_date = date(2012, 1, 1) if trans_date >= date(2012, 1, 1) else trans_date.replace(day=1)
            
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
        cur.close()
        conn.close()
        return
    
    print(f"\n{'='*70}")
    print("OPENING BALANCE ENTRIES TO CREATE")
    print(f"{'='*70}\n")
    
    for entry in opening_entries:
        print(f"Account: {entry['bank_name']}")
        print(f"Date: {entry['date']}")
        print(f"Amount: ${entry['balance']:,.2f}")
        print(f"Type: {'Revenue (positive balance)' if entry['balance'] > 0 else 'Expense (negative balance)'}")
        print(f"Description: {entry['description']}\n")
    
    print(f"{'='*70}")
    response = input(f"\nCreate {len(opening_entries)} opening balance entries? (yes/no): ")
    
    if response.strip().lower() != 'yes':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        return
    
    # Create opening balance receipts
    print("\n📝 Creating opening balance entries...")
    
    created = 0
    for entry in opening_entries:
        # For positive balances, put in revenue field
        # For negative balances, put in gross_amount field
        revenue = entry['balance'] if entry['balance'] > 0 else None
        gross = abs(entry['balance']) if entry['balance'] < 0 else None
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                mapped_bank_account_id,
                gross_amount,
                revenue,
                created_from_banking,
                source_system,
                description,
                verified_source,
                is_verified_banking,
                potential_duplicate,
                category
            ) VALUES (
                %s, %s, %s, %s, TRUE, 'OPENING_BALANCE', %s, 'OPENING_BALANCE', TRUE, FALSE, 'Opening Balance'
            ) RETURNING receipt_id
        """, (
            entry['date'],
            entry['bank_id'],
            gross,
            revenue,
            entry['description']
        ))
        
        receipt_id = cur.fetchone()[0]
        created += 1
        print(f"  ✅ Created receipt {receipt_id} for {entry['bank_name']}: ${entry['balance']:,.2f}")
    
    conn.commit()
    print(f"\n✅ Successfully created {created} opening balance entries")
    
    # Verify
    print("\n📊 Verification - All 2012 receipts with opening balances:")
    cur.execute("""
        SELECT 
            receipt_date,
            mapped_bank_account_id,
            COALESCE(revenue, gross_amount) as amount,
            category,
            description
        FROM receipts
        WHERE source_system = 'OPENING_BALANCE'
        ORDER BY receipt_date
    """)
    
    for row in cur.fetchall():
        print(f"  {row[0]} | Bank {row[1]} | ${row[2]:,.2f} | {row[3]} | {row[4]}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
