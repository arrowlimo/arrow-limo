#!/usr/bin/env python3
"""
Create banking event receipts for Scotia 2012 (account 903990106011).
Apply same successful pattern as CIBC accounts.
"""

import psycopg2
import hashlib
import sys

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
    write_mode = '--write' in sys.argv
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("SCOTIA 2012 BANKING EVENT RECEIPT CREATION")
    print("=" * 80)
    print(f"Mode: {'WRITE' if write_mode else 'DRY RUN'}")
    print()
    
    # Categories for Scotia
    categories = [
        {
            'name': 'ATM Withdrawals',
            'patterns': ['%ATM%', '%ABM%'],
            'category': 'Cash Withdrawal',
            'vendor': 'Scotia ATM'
        },
        {
            'name': 'POS Purchases',
            'patterns': ['%POS%PURCHASE%', '%DEBIT PURCHASE%'],
            'category': 'Business Expense',
            'vendor': 'POS Purchase'
        },
        {
            'name': 'Pre-Auth Holds',
            'patterns': ['%PRE-AUTH%', '%PREAUTH%'],
            'category': 'Pre-Authorization',
            'vendor': 'Pre-Auth Hold'
        },
        {
            'name': 'Banking Fees',
            'patterns': ['%FEE%', '%SERVICE CHARGE%', '%MONTHLY CHARGE%'],
            'category': 'Banking Fees',
            'vendor': 'Scotia Bank'
        },
        {
            'name': 'NSF/Reversals',
            'patterns': ['%NSF%'],
            'category': 'NSF/Reversal',
            'vendor': 'Scotia Bank'
        },
        {
            'name': 'Transfers',
            'patterns': ['%TRANSFER%', '%XFER%'],
            'category': 'Internal Transfer',
            'vendor': 'Scotia Internal'
        },
        {
            'name': 'Withdrawals',
            'patterns': ['%WITHDRAWAL%', '%WD %'],
            'category': 'Cash Withdrawal',
            'vendor': 'Scotia Branch'
        }
    ]
    
    total_created = 0
    total_skipped = 0
    category_stats = {}
    
    for cat in categories:
        print(f"\nProcessing {cat['name']}...")
        
        # Build WHERE clause
        pattern_conditions = ' OR '.join(['UPPER(description) LIKE %s'] * len(cat['patterns']))
        
        query = f"""
            SELECT 
                transaction_id,
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE account_number = '903990106011'
                AND EXTRACT(YEAR FROM transaction_date) = 2012
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
            source_hash = create_source_hash(txn_id, date, amount)
            
            if check_receipt_exists(cur, source_hash):
                skipped += 1
                continue
            
            if write_mode:
                cur.execute("""
                    INSERT INTO receipts (
                        source_system, source_reference, receipt_date,
                        vendor_name, description, gross_amount, category,
                        mapped_bank_account_id, source_hash, created_at,
                        created_from_banking, document_type
                    ) VALUES (
                        'Scotia_903990106011_Banking', %s, %s, %s, %s, %s,
                        %s, %s, %s, CURRENT_TIMESTAMP,
                        true, 'banking_transaction'
                    )
                    RETURNING id
                """, (
                    f"banking_{txn_id}",
                    date,
                    cat['vendor'],
                    desc or f"{cat['name']} - {date}",
                    amount,
                    cat['category'],
                    txn_id,
                    source_hash
                ))
                
                receipt_id = cur.fetchone()[0]
                
                cur.execute("""
                    UPDATE banking_transactions
                    SET receipt_id = %s
                    WHERE transaction_id = %s
                """, (receipt_id, txn_id))
                
                created += 1
            else:
                created += 1
        
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
        # Verify
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as total_debits,
                COUNT(CASE WHEN debit_amount > 0 AND receipt_id IS NOT NULL THEN 1 END) as matched_debits
            FROM banking_transactions
            WHERE account_number = '903990106011'
                AND EXTRACT(YEAR FROM transaction_date) = 2012
        """)
        total, matched = cur.fetchone()
        match_rate = 100 * matched / total if total > 0 else 0
        
        print("\n" + "=" * 80)
        print("VERIFICATION")
        print("=" * 80)
        print(f"Scotia 2012 debits: {matched}/{total} matched ({match_rate:.1f}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
