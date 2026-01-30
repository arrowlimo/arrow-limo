#!/usr/bin/env python3
"""
Create receipts for banking events that don't have physical receipts:
- Banking fees (service charges, NSF fees, etc.)
- Cash withdrawals (ATM, teller)
- NSF fees and reversals

This allows tracking these expenses even though no paper receipt exists.
"""

import os
import sys
import psycopg2
import hashlib
from datetime import datetime
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def generate_source_hash(account, date, desc, amount):
    """Generate unique hash for receipt."""
    hash_input = f"banking_event|{account}|{date}|{desc}|{amount}"
    return hashlib.sha256(hash_input.encode()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description='Create receipts for banking events')
    parser.add_argument('--write', action='store_true', help='Write receipts to database')
    parser.add_argument('--year', type=int, help='Limit to specific year')
    args = parser.parse_args()
    
    print("=" * 100)
    print("CREATE RECEIPTS FOR BANKING EVENTS")
    print("=" * 100)
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    if args.year:
        print(f"Year filter: {args.year}")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    year_filter = f"AND EXTRACT(YEAR FROM transaction_date) = {args.year}" if args.year else ""
    
    # Step 1: Find banking fees
    print("\n[1] Finding banking fees...")
    
    cur.execute(f"""
        SELECT 
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount
        FROM banking_transactions
        WHERE debit_amount > 0
          AND (
              description ILIKE '%service charge%'
              OR description ILIKE '%NSF%'
              OR description ILIKE '%fee%'
              OR description ILIKE '%overdraft%'
              OR description ILIKE '%insufficient%'
          )
          AND NOT EXISTS (
              SELECT 1 FROM receipts 
              WHERE mapped_bank_account_id = transaction_id
          )
          {year_filter}
        ORDER BY transaction_date
    """)
    
    banking_fees = cur.fetchall()
    print(f"    Found {len(banking_fees)} banking fee transactions")
    
    # Step 2: Find cash withdrawals
    print("\n[2] Finding cash withdrawals...")
    
    cur.execute(f"""
        SELECT 
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount
        FROM banking_transactions
        WHERE debit_amount > 0
          AND (
              description ILIKE '%ATM%'
              OR description ILIKE '%cash%withdrawal%'
              OR description ILIKE '%ABM%'
              OR description ILIKE '%WITHDRAWAL%CASH%'
              OR description ILIKE '%TELLER%CASH%'
          )
          AND NOT EXISTS (
              SELECT 1 FROM receipts 
              WHERE mapped_bank_account_id = transaction_id
          )
          {year_filter}
        ORDER BY transaction_date
    """)
    
    cash_withdrawals = cur.fetchall()
    print(f"    Found {len(cash_withdrawals)} cash withdrawal transactions")
    
    # Step 3: Find NSF reversals
    print("\n[3] Finding NSF reversals...")
    
    cur.execute(f"""
        SELECT 
            transaction_id,
            account_number,
            transaction_date,
            description,
            debit_amount,
            credit_amount
        FROM banking_transactions
        WHERE (
              description ILIKE '%NSF%REVERSAL%'
              OR description ILIKE '%RETURNED%ITEM%'
              OR description ILIKE '%DISHON%'
              OR (description ILIKE '%NSF%' AND credit_amount > 0)
          )
          AND NOT EXISTS (
              SELECT 1 FROM receipts 
              WHERE mapped_bank_account_id = transaction_id
          )
          {year_filter}
        ORDER BY transaction_date
    """)
    
    nsf_events = cur.fetchall()
    print(f"    Found {len(nsf_events)} NSF/reversal transactions")
    
    # Step 4: Prepare receipt records
    print("\n[4] Preparing receipt records...")
    
    receipts_to_create = []
    
    # Banking fees
    for trans in banking_fees:
        trans_id, account, date, desc, amount = trans
        source_hash = generate_source_hash(account, date, desc, amount)
        
        receipts_to_create.append({
            'type': 'BANKING_FEE',
            'transaction_id': trans_id,
            'date': date,
            'vendor': 'Bank Service Charge',
            'description': desc,
            'amount': amount,
            'category': 'Bank Charges',
            'source_hash': source_hash
        })
    
    # Cash withdrawals
    for trans in cash_withdrawals:
        trans_id, account, date, desc, amount = trans
        source_hash = generate_source_hash(account, date, desc, amount)
        
        receipts_to_create.append({
            'type': 'CASH_WITHDRAWAL',
            'transaction_id': trans_id,
            'date': date,
            'vendor': 'Cash Withdrawal',
            'description': desc,
            'amount': amount,
            'category': 'Cash Withdrawal',
            'source_hash': source_hash
        })
    
    # NSF events
    for trans in nsf_events:
        trans_id, account, date, desc, debit, credit = trans
        amount = debit if debit else credit
        source_hash = generate_source_hash(account, date, desc, amount)
        
        receipts_to_create.append({
            'type': 'NSF_EVENT',
            'transaction_id': trans_id,
            'date': date,
            'vendor': 'NSF Event',
            'description': desc,
            'amount': amount,
            'category': 'NSF/Reversal',
            'source_hash': source_hash
        })
    
    print(f"    Prepared {len(receipts_to_create)} receipt records")
    
    # Step 5: Show summary by type
    print("\n[5] Summary by type:")
    
    by_type = {}
    total_amount = {}
    for receipt in receipts_to_create:
        rtype = receipt['type']
        by_type[rtype] = by_type.get(rtype, 0) + 1
        total_amount[rtype] = total_amount.get(rtype, 0) + receipt['amount']
    
    for rtype in sorted(by_type.keys()):
        print(f"    {rtype}: {by_type[rtype]} receipts, ${total_amount[rtype]:,.2f}")
    
    # Show samples
    if receipts_to_create:
        print("\n[6] Sample receipts (first 10):")
        for receipt in receipts_to_create[:10]:
            print(f"    {receipt['date']} | {receipt['vendor']} | ${receipt['amount']:.2f}")
            print(f"      {receipt['description'][:70]}")
    
    # Step 6: Write to database
    if args.write and receipts_to_create:
        print("\n" + "=" * 100)
        print(f"[7] Writing {len(receipts_to_create)} receipts to database...")
        
        inserted = 0
        skipped = 0
        
        for receipt in receipts_to_create:
            # Check if receipt already exists by hash
            cur.execute("""
                SELECT id FROM receipts WHERE source_hash = %s
            """, (receipt['source_hash'],))
            
            if cur.fetchone():
                skipped += 1
                continue
            
            # Insert receipt
            cur.execute("""
                INSERT INTO receipts (
                    source_system,
                    source_reference,
                    receipt_date,
                    vendor_name,
                    description,
                    gross_amount,
                    category,
                    mapped_bank_account_id,
                    source_hash,
                    created_at,
                    created_from_banking,
                    document_type
                ) VALUES (
                    'banking_event',
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    true,
                    %s
                )
            """, (
                f"banking_{receipt['transaction_id']}",
                receipt['date'],
                receipt['vendor'],
                receipt['description'],
                receipt['amount'],
                receipt['category'],
                receipt['transaction_id'],
                receipt['source_hash'],
                datetime.now(),
                receipt['type']
            ))
            inserted += 1
        
        conn.commit()
        print(f"    ✓ Inserted {inserted} new receipts")
        if skipped > 0:
            print(f"    [WARN]  Skipped {skipped} duplicate receipts (already exist)")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*) 
            FROM receipts 
            WHERE created_from_banking = true
        """)
        total_banking_receipts = cur.fetchone()[0]
        print(f"    Total banking-generated receipts: {total_banking_receipts}")
    
    elif args.write:
        print("\n[WARN]  No receipts to create")
    else:
        print("\n💡 Run with --write to create these receipts in database")
    
    print("\n" + "=" * 100)
    print("COMPLETE")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
