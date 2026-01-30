"""
Import missing Scotia Bank January 2, 2013 transactions.
These transactions exist in account 1010 (QuickBooks) with no descriptions,
but are missing from the proper Scotia account 903990106011.

Based on PDF statement and account 1010 amounts.
"""

import psycopg2
import hashlib
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def generate_hash(date, description, debit, credit):
    """Generate deterministic hash for duplicate detection."""
    hash_input = f"903990106011|{date}|{description}|{debit:.2f}|{credit:.2f}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()

# January 2, 2013 transactions from PDF balance forward section
# Opening balance from Dec 31, 2012: 952.04
# These are ALL the transactions from the balance forward page
transactions = [
    # Date, Description, Debit (W), Credit (D), Expected Balance
    ('2013-01-02', 'BALANCE FORWARD', 0.00, 0.00, 952.04),
    
    # Deposits (from PDF DEPOSIT/CREDIT column)
    ('2013-01-02', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 193.00, None),
    ('2013-01-02', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 594.98, None),
    ('2013-01-02', 'DEPOSIT 0873847000019 00001 DEBITCD DEP CR CHASE PAYMENTECH', 0.00, 102.35, None),
    ('2013-01-02', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 165.00, None),
    ('2013-01-02', 'DEPOSIT 0973847000019 00001 MCARD DEP CR CHASE PAYMENTECH', 0.00, 205.00, None),
    ('2013-01-02', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 170.78, None),
    ('2013-01-02', 'DEPOSIT 0873847000019 00001 VISA DEP CR CHASE PAYMENTECH', 0.00, 1120.00, None),
    
    # Withdrawals (from PDF WITHDRAWAL/DEBITS column)
    ('2013-01-02', 'RENT/LEASES IA0001<HEFFNERPYMT> ACE TRUCK RENTALS LTD.', 2695.40, 0.00, None),
    ('2013-01-02', 'AUTO LEASE HEFFNER AUTO FC', 889.87, 0.00, None),
    ('2013-01-02', 'AUTO LEASE HEFFNER AUTO FC', 471.98, 0.00, None),
    ('2013-01-02', 'POINT OF SALE PURCHASE CINEPLEX #3132 QPS RED DEER ABCD', 54.01, 0.00, None),
    ('2013-01-02', 'DEPOSIT 0873847000019 00001 VISA DEP DR CHASE PAYMENTECH', 788.22, 0.00, None),
    ('2013-01-02', 'DEPOSIT 0973847000019 00001 MCARD FEE DR CHASE PAYMENTECH', 419.35, 0.00, None),
    ('2013-01-02', 'OVERDRAWN HANDLING CHGS', 20.00, 0.00, None),
    ('2013-01-02', 'CHQ 114 3700531481', 841.00, 0.00, None),
    ('2013-01-02', 'CHQ 112 2500490143', 801.41, 0.00, None),
    ('2013-01-02', 'OVERDRAWN HANDLING CHGS', 10.00, 0.00, None),
]

def main():
    parser = argparse.ArgumentParser(description='Import Scotia Jan 2, 2013 transactions')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("SCOTIA BANK JANUARY 2, 2013 DATA IMPORT")
    print("="*80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN (preview only)'}")
    print()
    
    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date = '2013-01-02'
    """)
    existing_count = cur.fetchone()[0]
    print(f"Existing Jan 2, 2013 transactions in 903990106011: {existing_count}")
    
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '1010'
        AND transaction_date = '2013-01-02'
    """)
    qb_count = cur.fetchone()[0]
    print(f"Existing Jan 2, 2013 transactions in 1010 (QB): {qb_count}")
    print()
    
    # Check for duplicates
    print("Checking for duplicates...")
    new_transactions = []
    duplicate_count = 0
    
    for date, desc, debit, credit, balance in transactions:
        source_hash = generate_hash(date, desc, debit, credit)
        
        cur.execute("""
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = '903990106011'
            AND transaction_date = %s
            AND COALESCE(debit_amount, 0) = %s
            AND COALESCE(credit_amount, 0) = %s
            AND description = %s
        """, (date, debit, credit, desc))
        
        if cur.fetchone():
            duplicate_count += 1
            print(f"  SKIP (duplicate): {date} | {desc[:50]} | D:{debit} C:{credit}")
        else:
            new_transactions.append((date, desc, debit, credit, balance, source_hash))
    
    print(f"\nNew transactions to import: {len(new_transactions)}")
    print(f"Duplicates skipped: {duplicate_count}")
    print()
    
    if new_transactions:
        print("Transactions to import:")
        print("-"*80)
        running_balance = 952.04
        total_debits = 0
        total_credits = 0
        
        for date, desc, debit, credit, balance, source_hash in new_transactions:
            if debit > 0:
                running_balance -= debit
                total_debits += debit
                amt_str = f"DEBIT:  ${debit:>9.2f}"
            elif credit > 0:
                running_balance += credit
                total_credits += credit
                amt_str = f"CREDIT: ${credit:>9.2f}"
            else:
                amt_str = "BALANCE FORWARD"
            
            desc_short = desc[:50].ljust(50)
            print(f"  {date} | {desc_short} | {amt_str} | Bal: ${running_balance:>10.2f}")
        
        print("-"*80)
        print(f"Total debits:  ${total_debits:>10.2f}")
        print(f"Total credits: ${total_credits:>10.2f}")
        print(f"Net change:    ${(total_credits - total_debits):>10.2f}")
        print(f"Ending balance: ${running_balance:>10.2f}")
        print()
        
        if args.write:
            print("WRITING TO DATABASE...")
            inserted = 0
            
            for date, desc, debit, credit, balance, source_hash in new_transactions:
                debit_val = debit if debit > 0 else None
                credit_val = credit if credit > 0 else None
                
                cur.execute("""
                    INSERT INTO banking_transactions (
                        account_number, transaction_date, description,
                        debit_amount, credit_amount, source_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, ('903990106011', date, desc, debit_val, credit_val, source_hash))
                
                inserted += 1
            
            conn.commit()
            print(f"✓ Successfully inserted {inserted} transactions")
            print()
            
            # Verify
            cur.execute("""
                SELECT COUNT(*) FROM banking_transactions
                WHERE account_number = '903990106011'
                AND transaction_date = '2013-01-02'
            """)
            final_count = cur.fetchone()[0]
            print(f"Final count for Jan 2, 2013 in Scotia account: {final_count}")
            
        else:
            print("DRY-RUN: No changes made. Use --write to apply.")
    else:
        print("No new transactions to import (all already exist).")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
