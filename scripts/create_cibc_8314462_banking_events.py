#!/usr/bin/env python3
"""
Create banking event receipts for CIBC account 8314462 unmatched transactions.
Based on successful pattern from accounts 0228362 and 3648117.
"""

import psycopg2
import hashlib
import sys
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def create_source_hash(transaction_id, date, amount):
    """Create deterministic hash for duplicate detection."""
    hash_input = f"{transaction_id}_{date}_{amount}"
    return hashlib.sha256(hash_input.encode()).hexdigest()

def check_receipt_exists(cur, source_hash):
    """Check if receipt with this source_hash already exists."""
    cur.execute("SELECT id FROM receipts WHERE source_hash = %s", (source_hash,))
    return cur.fetchone() is not None

def main():
    # Check for --write flag
    write_mode = '--write' in sys.argv
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CIBC 8314462 BANKING EVENT RECEIPT CREATION")
    print("=" * 80)
    print(f"Mode: {'WRITE' if write_mode else 'DRY RUN'}")
    print()
    
    # Categories to process
    categories = [
        {
            'name': 'ATM Withdrawals',
            'patterns': ['%ATM%', '%ABM%', '%AUTOMATED BANKING MACHINE%'],
            'category': 'Cash Withdrawal',
            'vendor': 'CIBC ATM'
        },
        {
            'name': 'Branch Withdrawals',
            'patterns': ['%BRANCH%WITHDRAWAL%'],
            'category': 'Cash Withdrawal',
            'vendor': 'CIBC Branch'
        },
        {
            'name': 'Banking Fees',
            'patterns': ['%FEE%', '%SERVICE CHARGE%', '%MONTHLY CHARGE%'],
            'category': 'Banking Fees',
            'vendor': 'CIBC'
        },
        {
            'name': 'Debit Memos',
            'patterns': ['%DEBIT MEMO%', '%DB MEMO%'],
            'category': 'Bank Charges',
            'vendor': 'CIBC'
        },
        {
            'name': 'Internal Transfers',
            'patterns': ['%TRANSFER%', '%XFER%'],
            'category': 'Internal Transfer',
            'vendor': 'CIBC Internal'
        }
    ]
    
    total_created = 0
    total_skipped = 0
    category_stats = {}
    
    for cat in categories:
        print(f"\nProcessing {cat['name']}...")
        
        # Build WHERE clause for patterns
        pattern_conditions = ' OR '.join(['UPPER(description) LIKE %s'] * len(cat['patterns']))
        
        query = f"""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE account_number = '8314462'
                AND debit_amount > 0
                AND receipt_id IS NULL
                AND ({pattern_conditions})
            ORDER BY transaction_date
        """
        
        cur.execute(query, [p.upper() for p in cat['patterns']])
        transactions = cur.fetchall()
        
        created = 0
        skipped = 0
        
        for txn_id, date, desc, amount in transactions:
            # Create source hash
            source_hash = create_source_hash(txn_id, date, amount)
            
            # Check if already exists
            if check_receipt_exists(cur, source_hash):
                skipped += 1
                continue
            
            if write_mode:
                # Create receipt
                cur.execute("""
                    INSERT INTO receipts (
                        source_system, source_reference, receipt_date,
                        vendor_name, description, gross_amount, category,
                        mapped_bank_account_id, source_hash, created_at,
                        created_from_banking, document_type
                    ) VALUES (
                        'CIBC_8314462_Banking', %s, %s, %s, %s, %s,
                        %s, %s, %s, CURRENT_TIMESTAMP,
                        true, 'banking_transaction'
                    )
                    RETURNING id
                """, (
                    f"banking_{txn_id}",  # source_reference
                    date,                  # receipt_date
                    cat['vendor'],         # vendor_name
                    desc or f"{cat['name']} - {date}",  # description
                    amount,                # gross_amount
                    cat['category'],       # category
                    txn_id,               # mapped_bank_account_id
                    source_hash           # source_hash
                ))
                
                receipt_id = cur.fetchone()[0]
                
                # Link to banking transaction
                cur.execute("""
                    UPDATE banking_transactions
                    SET receipt_id = %s
                    WHERE transaction_id = %s
                """, (receipt_id, txn_id))
                
                created += 1
            else:
                created += 1  # Count for dry run
        
        category_stats[cat['name']] = {
            'created': created,
            'skipped': skipped,
            'amount': sum(t[3] for t in transactions if not check_receipt_exists(cur, create_source_hash(t[0], t[1], t[3])))
        }
        
        total_created += created
        total_skipped += skipped
        
        print(f"  Found {len(transactions)} transactions")
        print(f"  {'Would create' if not write_mode else 'Created'} {created} receipts")
        if skipped > 0:
            print(f"  Skipped {skipped} duplicates")
    
    if write_mode:
        conn.commit()
        print("\n" + "=" * 80)
        print("CHANGES COMMITTED TO DATABASE")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("DRY RUN - NO CHANGES MADE")
        print("Run with --write flag to apply changes")
        print("=" * 80)
    
    # Summary
    print("\nSummary by Category:")
    for name, stats in category_stats.items():
        if stats['created'] > 0 or stats['skipped'] > 0:
            print(f"  {name}: {stats['created']} receipts, ${stats['amount']:,.2f}")
    
    print(f"\nTotal receipts {'created' if write_mode else 'to create'}: {total_created}")
    if total_skipped > 0:
        print(f"Total duplicates skipped: {total_skipped}")
    
    if write_mode:
        # Verify match rate improvement
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total_debits,
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NOT NULL THEN 1 END) as matched_debits
            FROM banking_transactions
            WHERE account_number = '8314462'
        """)
        total, matched = cur.fetchone()
        match_rate = 100 * matched / total if total > 0 else 0
        
        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)
        print(f"Account 8314462 debits: {matched}/{total} matched ({match_rate:.1f}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
