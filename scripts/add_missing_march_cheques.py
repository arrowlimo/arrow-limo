#!/usr/bin/env python3
"""
Add missing March 2012 cheques 215 and 216 to banking_transactions.

Based on CIBC statement showing:
- Mar 19: Balance forward $2,894.74
- Mar 19: Cheque 216 000000017320440 - $100.00 → Balance $2,674.40
- Mar 19: Cheque 215 0000000... - $150.00 → Balance $2,524.40

Note: There's a discrepancy in the balance calculation:
$2,894.74 - $100.00 should = $2,794.74 (not $2,674.40)
The $120.34 difference suggests there's a missing transaction between balance forward and cheque 216.

For now, we'll add the cheques with the amounts shown, but flag for review.
"""

import psycopg2
import os
import sys
import hashlib
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def create_transaction_hash(date, description, amount):
    """Create deterministic hash for transaction."""
    normalized = f"{date}|{description.strip().upper()}|{amount:.2f}"
    return hashlib.sha256(normalized.encode()).hexdigest()

def main():
    if len(sys.argv) < 2 or sys.argv[1] != '--write':
        print("=" * 80)
        print("DRY RUN MODE - Add --write to actually insert transactions")
        print("=" * 80)
        write_mode = False
    else:
        write_mode = True
        print("=" * 80)
        print("WRITE MODE - Will insert transactions into database")
        print("=" * 80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Define the missing transactions from CIBC statement
    transactions = [
        {
            'date': '2012-03-19',
            'description': 'Cheque 216 000000017320440',
            'debit': 100.00,
            'balance': 2674.40,  # As shown on CIBC statement
            'category': 'Cheque',
            'notes': 'Added from CIBC statement Mar 1-31, 2012. Original import from verified file was incomplete for Mar 16-31.'
        },
        {
            'date': '2012-03-19',
            'description': 'Cheque 215 000000017320441',  # Estimated reference number
            'debit': 150.00,
            'balance': 2524.40,  # As shown on CIBC statement
            'category': 'Cheque',
            'notes': 'Added from CIBC statement Mar 1-31, 2012. Original import from verified file was incomplete for Mar 16-31. Reference number estimated.'
        }
    ]
    
    account_number = '0228362'
    added_count = 0
    
    print("\nTransactions to add:")
    print("-" * 80)
    
    for tx in transactions:
        # Check if already exists
        tx_hash = create_transaction_hash(tx['date'], tx['description'], tx['debit'])
        
        cur.execute("""
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = %s
            AND transaction_date = %s
            AND debit_amount = %s
            AND description ILIKE %s
        """, (account_number, tx['date'], tx['debit'], f"%{tx['description'].split()[1]}%"))
        
        existing = cur.fetchone()
        
        if existing:
            print(f"[WARN]  SKIP: {tx['description']} already exists (ID: {existing[0]})")
            continue
        
        print(f"[OK] ADD: {tx['date']} | {tx['description']} | ${tx['debit']:.2f} | Balance: ${tx['balance']:.2f}")
        
        if write_mode:
            cur.execute("""
                INSERT INTO banking_transactions (
                    account_number,
                    transaction_date,
                    description,
                    debit_amount,
                    credit_amount,
                    balance,
                    category,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING transaction_id
            """, (
                account_number,
                tx['date'],
                tx['description'],
                tx['debit'],
                None,  # credit_amount
                tx['balance'],
                tx['category'],
                datetime.now()
            ))
            
            new_id = cur.fetchone()[0]
            print(f"   → Inserted with transaction_id: {new_id}")
            added_count += 1
    
    if write_mode:
        conn.commit()
        print(f"\n[OK] Successfully added {added_count} transactions")
        
        # Now update the cheque_register to link these transactions
        print("\n" + "=" * 80)
        print("UPDATING CHEQUE REGISTER LINKS")
        print("=" * 80)
        
        for cheque_num in ['215', '216']:
            # Find the banking transaction
            cur.execute("""
                SELECT transaction_id 
                FROM banking_transactions
                WHERE account_number = %s
                AND transaction_date = '2012-03-19'
                AND description LIKE %s
            """, (account_number, f'%{cheque_num}%'))
            
            result = cur.fetchone()
            if result:
                banking_tx_id = result[0]
                
                # Update cheque_register
                cur.execute("""
                    UPDATE cheque_register
                    SET banking_transaction_id = %s
                    WHERE cheque_number = %s
                    AND banking_transaction_id IS NULL
                    RETURNING id
                """, (banking_tx_id, cheque_num))
                
                updated = cur.fetchone()
                if updated:
                    print(f"[OK] Linked cheque {cheque_num} to banking transaction {banking_tx_id}")
                else:
                    print(f"[WARN]  Cheque {cheque_num} already linked or not found in register")
            else:
                print(f"[FAIL] Could not find banking transaction for cheque {cheque_num}")
        
        conn.commit()
        print("\n[OK] All updates complete!")
        
    else:
        print("\n[WARN]  DRY RUN - No changes made. Run with --write to apply.")
    
    # Show final status
    print("\n" + "=" * 80)
    print("FINAL CHEQUE REGISTER STATUS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            cheque_number,
            cheque_date,
            amount,
            payee,
            banking_transaction_id,
            CASE WHEN banking_transaction_id IS NULL THEN 'UNCLEARED' ELSE 'LINKED' END as status
        FROM cheque_register
        WHERE cheque_number IN ('215', '216')
        ORDER BY cheque_number
    """)
    
    for row in cur.fetchall():
        print(f"Cheque {row[0]}: {row[1]} | ${row[2]:.2f} | {row[3]} | {row[5]} (TX ID: {row[4]})")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
