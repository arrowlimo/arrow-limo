"""
Sync ALL Banking Transactions to Receipts Table
================================================

Creates receipts for ALL banking transactions (both credits and debits)
that don't already have receipts, ensuring complete banking statement
coverage while avoiding true duplicates.

Rules:
1. Skip if banking_transaction already has a receipt
2. Create receipt for each unlinked banking transaction
3. Detect TRUE duplicates: same date + amount + vendor (not recurring)
4. Preserve recurring transactions: same amount, different dates

Author: AI Agent
Date: December 19, 2025
"""

import psycopg2
import os
from datetime import datetime
import hashlib

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def generate_dedup_hash(transaction_date, amount, description):
    """Generate hash for deduplication: date + amount + vendor."""
    key = f"{transaction_date}|{abs(amount):.2f}|{(description or '').strip().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()


def main():
    print("="*70)
    print("SYNC ALL BANKING TRANSACTIONS TO RECEIPTS")
    print("="*70)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get all banking transactions without receipts
    print("\n1. Finding banking transactions without receipts...")
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            category,
            vendor_extracted,
            account_number,
            source_file
        FROM banking_transactions
        WHERE transaction_id NOT IN (
            SELECT banking_transaction_id 
            FROM receipts 
            WHERE banking_transaction_id IS NOT NULL
        )
        ORDER BY transaction_date, transaction_id
    """)
    
    unlinked = cur.fetchall()
    print(f"   Found {len(unlinked):,} unlinked banking transactions")
    
    if len(unlinked) == 0:
        print("\n✅ All banking transactions already have receipts!")
        conn.close()
        return
    
    # Build deduplication set from existing receipts
    print("\n2. Building deduplication index from existing receipts...")
    cur.execute("""
        SELECT receipt_date, gross_amount, vendor_name
        FROM receipts
        WHERE receipt_date IS NOT NULL
    """)
    
    existing_hashes = set()
    for row in cur.fetchall():
        hash_key = generate_dedup_hash(row[0], row[1], row[2])
        existing_hashes.add(hash_key)
    
    print(f"   Indexed {len(existing_hashes):,} existing receipt signatures")
    
    # Process unlinked transactions
    print("\n3. Creating receipts for unlinked banking transactions...")
    
    created_count = 0
    skipped_duplicates = 0
    credits_created = 0
    debits_created = 0
    
    for row in unlinked:
        transaction_id = row[0]
        transaction_date = row[1]
        description = row[2]
        debit_amount = row[3] or 0
        credit_amount = row[4] or 0
        category = row[5]
        vendor_extracted = row[6]
        account_number = row[7]
        source_file = row[8]
        
        # Determine if credit or debit
        is_credit = credit_amount > 0
        amount = credit_amount if is_credit else debit_amount
        
        # Check for true duplicate
        vendor_name = vendor_extracted or description or 'Unknown'
        hash_key = generate_dedup_hash(transaction_date, amount, vendor_name)
        
        if hash_key in existing_hashes:
            skipped_duplicates += 1
            print(f"   SKIP (duplicate): {transaction_date} | {vendor_name[:40]} | ${amount:,.2f}")
            continue
        
        # Determine expense account based on credit/debit
        if is_credit:
            # Credits are income/deposits
            expense_account = 'Income - Customer Payments' if 'DEPOSIT' in description.upper() else 'Income - Other'
            payment_method = 'Bank Deposit'
        else:
            # Debits are expenses
            expense_account = category or 'Expense - General'
            payment_method = 'Bank Debit'
        
        # Create receipt
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                gst_amount,
                net_amount,
                expense_account,
                payment_method,
                banking_transaction_id,
                created_from_banking,
                source_system,
                source_file,
                validation_status,
                comment
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            transaction_date,
            vendor_name,
            description,
            amount if is_credit else -amount,  # Credits positive, debits negative
            0,  # GST not known from banking
            amount if is_credit else -amount,
            expense_account,
            payment_method,
            transaction_id,
            True,  # created_from_banking
            'banking_sync',
            source_file,
            'auto_synced',
            f'Auto-created from banking transaction ({"credit" if is_credit else "debit"})'
        ))
        
        created_count += 1
        if is_credit:
            credits_created += 1
        else:
            debits_created += 1
        
        # Add to dedup set
        existing_hashes.add(hash_key)
        
        if created_count % 100 == 0:
            print(f"   Created {created_count:,} receipts...")
    
    conn.commit()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\nTotal unlinked banking transactions: {len(unlinked):,}")
    print(f"  ✅ Receipts created: {created_count:,}")
    print(f"     - Credits (deposits): {credits_created:,}")
    print(f"     - Debits (withdrawals): {debits_created:,}")
    print(f"  ⏭️  Skipped (duplicates): {skipped_duplicates:,}")
    
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)
    
    # Verify coverage
    cur.execute("""
        SELECT COUNT(*) 
        FROM banking_transactions
        WHERE transaction_id NOT IN (
            SELECT banking_transaction_id 
            FROM receipts 
            WHERE banking_transaction_id IS NOT NULL
        )
    """)
    
    remaining = cur.fetchone()[0]
    print(f"\nRemaining unlinked banking transactions: {remaining:,}")
    
    if remaining > 0:
        print(f"⚠️  Some transactions still unlinked (likely duplicates)")
    else:
        print(f"✅ ALL banking transactions now have receipts!")
    
    conn.close()
    print("\n✅ Sync complete!")


if __name__ == '__main__':
    main()
