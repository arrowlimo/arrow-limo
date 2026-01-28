#!/usr/bin/env python3
"""
Create receipts for all unmatched CIBC 1010 transactions (2013).

Since descriptions are blank, we'll categorize by:
- Large credits ($20K+): Monthly revenue deposits
- Small credits (<$1K): Cash deposits  
- Debits: Operating expenses (uncategorized)

This creates a baseline where all transactions have receipts,
even if they lack detail.
"""

import psycopg2
import os
import argparse
import hashlib

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def create_cibc_1010_receipts(dry_run=True):
    """Create receipts for CIBC 1010 transactions."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print(" " * 25 + "CREATE RECEIPTS FOR CIBC 1010 (2013)")
    print("=" * 100)
    print()
    
    if dry_run:
        print("DRY RUN MODE - No database changes will be made")
        print()
    
    # Get unmatched debits
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            debit_amount,
            description
        FROM banking_transactions
        WHERE account_number = '1010'
          AND EXTRACT(YEAR FROM transaction_date) = 2013
          AND debit_amount > 0
          AND receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    debits = cur.fetchall()
    print(f"Found {len(debits)} unmatched debits")
    
    # Get unmatched credits  
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            credit_amount,
            description
        FROM banking_transactions
        WHERE account_number = '1010'
          AND EXTRACT(YEAR FROM transaction_date) = 2013
          AND credit_amount > 0
          AND receipt_id IS NULL
        ORDER BY transaction_date
    """)
    
    credits = cur.fetchall()
    print(f"Found {len(credits)} unmatched credits")
    print()
    
    created_count = 0
    
    if not dry_run:
        # Create receipts for debits
        print(f"Creating receipts for {len(debits)} debits...")
        for trans_id, date, amount, desc in debits:
            source_ref = f"banking_{trans_id}"
            source_hash = hashlib.sha256(f"{trans_id}-{date}-{amount}".encode()).hexdigest()
            
            # Category based on amount (rough categorization)
            if amount < 100:
                category = "Operating Expenses"
                vendor = "Various - Small Expense"
            elif amount < 500:
                category = "Operating Expenses"
                vendor = "Various - Medium Expense"
            else:
                category = "Operating Expenses"
                vendor = "Various - Large Expense"
            
            description = desc.strip() if desc and desc.strip() else f"CIBC 1010 debit ${amount:.2f}"
            
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
                    'CIBC_1010_Import',
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, true, 'banking_transaction'
                )
                RETURNING id
            """, (
                source_ref, date, vendor, description,
                amount, category, trans_id, source_hash
            ))
            
            receipt_id = cur.fetchone()[0]
            
            # Link banking transaction to receipt
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
            """, (receipt_id, trans_id))
            
            created_count += 1
        
        print(f"  Created {created_count} debit receipts")
        print()
        
        # Create receipts for credits
        print(f"Creating receipts for {len(credits)} credits...")
        credit_count = 0
        
        for trans_id, date, amount, desc in credits:
            source_ref = f"banking_{trans_id}"
            source_hash = hashlib.sha256(f"{trans_id}-{date}-{amount}".encode()).hexdigest()
            
            # Categorize credits
            if amount >= 20000:
                category = "Revenue Deposit"
                vendor = "Monthly Revenue Deposit"
                description = f"Monthly charter revenue deposit - ${amount:,.2f}"
            elif amount >= 1000:
                category = "Revenue Deposit"
                vendor = "Revenue Deposit"
                description = f"Charter revenue deposit - ${amount:,.2f}"
            else:
                category = "Revenue Deposit"
                vendor = "Cash Deposit"
                description = f"Cash deposit - ${amount:,.2f}"
            
            # Note: Credits reduce expenses (negative amount for receipts)
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
                    'CIBC_1010_Import',
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, true, 'banking_transaction'
                )
                RETURNING id
            """, (
                source_ref, date, vendor, description,
                -amount,  # Negative for credits (income)
                category, trans_id, source_hash
            ))
            
            receipt_id = cur.fetchone()[0]
            
            # Link banking transaction to receipt
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
            """, (receipt_id, trans_id))
            
            credit_count += 1
        
        print(f"  Created {credit_count} credit receipts")
        print()
        
        conn.commit()
        
        # Verify
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE account_number = '1010'
              AND receipt_id IS NOT NULL
        """)
        matched = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE account_number = '1010'
        """)
        total = cur.fetchone()[0]
        
        print(f"Verification: {matched}/{total} transactions now have receipts ({matched/total*100:.1f}%)")
        print()
        
    else:
        print("DRY RUN - Would create:")
        print(f"  {len(debits)} debit receipts (Operating Expenses)")
        print(f"  {len(credits)} credit receipts (Revenue Deposits)")
        print()
        print("Add --write flag to apply")
    
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create receipts for CIBC 1010 transactions')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    create_cibc_1010_receipts(dry_run=not args.write)
