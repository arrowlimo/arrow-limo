#!/usr/bin/env python3
"""
Create banking event receipts for CIBC 0228362.
Focus on easy patterns: ATM withdrawals, branch withdrawals, bank fees.
"""

import psycopg2
import os
import argparse
import hashlib

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def create_banking_events_0228362(dry_run=True):
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print(" " * 20 + "CREATE BANKING EVENT RECEIPTS - CIBC 0228362")
    print("=" * 100)
    print()
    
    if dry_run:
        print("DRY RUN MODE - No database changes will be made")
        print()
    
    # Pattern 1: ABM/ATM Withdrawals
    print("[1] Processing ABM/ATM Withdrawals...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND debit_amount > 0
          AND receipt_id IS NULL
          AND (description ILIKE '%ABM%' OR description ILIKE '%ATM%')
        ORDER BY transaction_date
    """)
    
    atm_txns = cur.fetchall()
    print(f"    Found {len(atm_txns)} ATM/ABM withdrawals (${sum(t[2] for t in atm_txns):,.2f})")
    
    # Pattern 2: Branch Withdrawals
    print("[2] Processing Branch Withdrawals...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND debit_amount > 0
          AND receipt_id IS NULL
          AND description ILIKE '%BRANCH%'
          AND description ILIKE '%WITHDRAWAL%'
        ORDER BY transaction_date
    """)
    
    branch_txns = cur.fetchall()
    print(f"    Found {len(branch_txns)} branch withdrawals (${sum(t[2] for t in branch_txns):,.2f})")
    
    # Pattern 3: Bank Fees/Charges
    print("[3] Processing Bank Fees/Charges...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND debit_amount > 0
          AND receipt_id IS NULL
          AND (description ILIKE '%FEE%' OR description ILIKE '%CHARGE%'
               OR description ILIKE '%SERVICE%')
        ORDER BY transaction_date
    """)
    
    fee_txns = cur.fetchall()
    print(f"    Found {len(fee_txns)} bank fees/charges (${sum(t[2] for t in fee_txns):,.2f})")
    
    # Pattern 4: Debit Memos
    print("[4] Processing Debit Memos...")
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND debit_amount > 0
          AND receipt_id IS NULL
          AND description ILIKE '%DEBIT MEMO%'
        ORDER BY transaction_date
    """)
    
    memo_txns = cur.fetchall()
    print(f"    Found {len(memo_txns)} debit memos (${sum(t[2] for t in memo_txns):,.2f})")
    print()
    
    total_txns = len(atm_txns) + len(branch_txns) + len(fee_txns) + len(memo_txns)
    total_amount = sum(t[2] for t in atm_txns + branch_txns + fee_txns + memo_txns)
    
    print(f"Total transactions to process: {total_txns} (${total_amount:,.2f})")
    print()
    
    if not dry_run:
        created = 0
        skipped = 0
        
        # Create ATM receipts
        for trans_id, date, amount, desc in atm_txns:
            source_ref = f"banking_{trans_id}"
            source_hash = hashlib.sha256(f"{trans_id}-{date}-{amount}".encode()).hexdigest()
            
            # Check if already exists
            cur.execute("SELECT id FROM receipts WHERE source_hash = %s", (source_hash,))
            if cur.fetchone():
                skipped += 1
                continue
            
            cur.execute("""
                INSERT INTO receipts (
                    source_system, source_reference, receipt_date,
                    vendor_name, description, gross_amount, category,
                    mapped_bank_account_id, source_hash, created_at,
                    created_from_banking, document_type
                ) VALUES (
                    'CIBC_0228362_Banking', %s, %s, 'Cash Withdrawal', %s, %s,
                    'Cash Withdrawal', %s, %s, CURRENT_TIMESTAMP,
                    true, 'banking_transaction'
                )
                RETURNING id
            """, (source_ref, date, desc or f"ATM withdrawal ${amount:.2f}",
                  amount, trans_id, source_hash))
            
            receipt_id = cur.fetchone()[0]
            
            cur.execute("UPDATE banking_transactions SET receipt_id = %s WHERE transaction_id = %s",
                       (receipt_id, trans_id))
            created += 1
        
        # Create Branch Withdrawal receipts
        for trans_id, date, amount, desc in branch_txns:
            source_ref = f"banking_{trans_id}"
            source_hash = hashlib.sha256(f"{trans_id}-{date}-{amount}".encode()).hexdigest()
            
            # Check if already exists
            cur.execute("SELECT id FROM receipts WHERE source_hash = %s", (source_hash,))
            if cur.fetchone():
                skipped += 1
                continue
            
            cur.execute("""
                INSERT INTO receipts (
                    source_system, source_reference, receipt_date,
                    vendor_name, description, gross_amount, category,
                    mapped_bank_account_id, source_hash, created_at,
                    created_from_banking, document_type
                ) VALUES (
                    'CIBC_0228362_Banking', %s, %s, 'Cash Withdrawal', %s, %s,
                    'Cash Withdrawal', %s, %s, CURRENT_TIMESTAMP,
                    true, 'banking_transaction'
                )
                RETURNING id
            """, (source_ref, date, desc or f"Branch withdrawal ${amount:.2f}",
                  amount, trans_id, source_hash))
            
            receipt_id = cur.fetchone()[0]
            
            cur.execute("UPDATE banking_transactions SET receipt_id = %s WHERE transaction_id = %s",
                       (receipt_id, trans_id))
            created += 1
        
        # Create Bank Fee receipts
        for trans_id, date, amount, desc in fee_txns:
            source_ref = f"banking_{trans_id}"
            source_hash = hashlib.sha256(f"{trans_id}-{date}-{amount}".encode()).hexdigest()
            
            # Check if already exists
            cur.execute("SELECT id FROM receipts WHERE source_hash = %s", (source_hash,))
            if cur.fetchone():
                skipped += 1
                continue
            
            # Categorize by description
            if 'NSF' in desc.upper():
                category = 'NSF/Reversal'
                vendor = 'NSF Fee'
            else:
                category = 'Banking Fees'
                vendor = 'Bank Charges & Interest'
            
            cur.execute("""
                INSERT INTO receipts (
                    source_system, source_reference, receipt_date,
                    vendor_name, description, gross_amount, category,
                    mapped_bank_account_id, source_hash, created_at,
                    created_from_banking, document_type
                ) VALUES (
                    'CIBC_0228362_Banking', %s, %s, %s, %s, %s,
                    %s, %s, %s, CURRENT_TIMESTAMP,
                    true, 'banking_transaction'
                )
                RETURNING id
            """, (source_ref, date, vendor, desc or f"Bank fee ${amount:.2f}",
                  amount, category, trans_id, source_hash))
            
            receipt_id = cur.fetchone()[0]
            
            cur.execute("UPDATE banking_transactions SET receipt_id = %s WHERE transaction_id = %s",
                       (receipt_id, trans_id))
            created += 1
        
        # Create Debit Memo receipts
        for trans_id, date, amount, desc in memo_txns:
            source_ref = f"banking_{trans_id}"
            source_hash = hashlib.sha256(f"{trans_id}-{date}-{amount}".encode()).hexdigest()
            
            # Check if already exists
            cur.execute("SELECT id FROM receipts WHERE source_hash = %s", (source_hash,))
            if cur.fetchone():
                skipped += 1
                continue
            
            # Try to categorize by description content
            if 'CRA' in desc.upper() or 'TAX' in desc.upper():
                category = 'Tax Payment'
                vendor = 'Canada Revenue Agency'
            else:
                category = 'Bank Charges'
                vendor = 'Debit Memo'
            
            cur.execute("""
                INSERT INTO receipts (
                    source_system, source_reference, receipt_date,
                    vendor_name, description, gross_amount, category,
                    mapped_bank_account_id, source_hash, created_at,
                    created_from_banking, document_type
                ) VALUES (
                    'CIBC_0228362_Banking', %s, %s, %s, %s, %s,
                    %s, %s, %s, CURRENT_TIMESTAMP,
                    true, 'banking_transaction'
                )
                RETURNING id
            """, (source_ref, date, vendor, desc or f"Debit memo ${amount:.2f}",
                  amount, category, trans_id, source_hash))
            
            receipt_id = cur.fetchone()[0]
            
            cur.execute("UPDATE banking_transactions SET receipt_id = %s WHERE transaction_id = %s",
                       (receipt_id, trans_id))
            created += 1
        
        conn.commit()
        
        print(f"Created {created} receipts successfully")
        print(f"Skipped {skipped} duplicates")
        print()
        
        # Verify
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NOT NULL THEN 1 END) as matched,
                COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total
            FROM banking_transactions
            WHERE account_number = '0228362'
        """)
        matched, total = cur.fetchone()
        
        print(f"Verification: {matched}/{total} debits now matched ({matched/total*100:.1f}%)")
        print(f"Improvement: +{created} receipts, +{created/total*100:.1f}% coverage")
        
    else:
        print("DRY RUN - Would create:")
        print(f"  {len(atm_txns)} ATM withdrawal receipts")
        print(f"  {len(branch_txns)} branch withdrawal receipts")
        print(f"  {len(fee_txns)} bank fee receipts")
        print(f"  {len(memo_txns)} debit memo receipts")
        print(f"  Total: {total_txns} receipts (${total_amount:,.2f})")
        print()
        print("Add --write flag to apply")
    
    print()
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create banking event receipts for CIBC 0228362')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    create_banking_events_0228362(dry_run=not args.write)
