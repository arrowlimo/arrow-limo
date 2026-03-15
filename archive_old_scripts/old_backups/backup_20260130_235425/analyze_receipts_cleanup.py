#!/usr/bin/env python3
"""
Analyze current receipts and verified banking records before cleanup.
"""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    print('=== CURRENT RECEIPTS STATUS ===\n')

    # Total receipts
    cur.execute('SELECT COUNT(*) FROM receipts')
    total_receipts = cur.fetchone()[0]
    print(f'Total receipts: {total_receipts:,}')

    # Receipts linked to banking
    cur.execute('SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NOT NULL')
    banking_linked = cur.fetchone()[0]
    print(f'Receipts linked to banking: {banking_linked:,}')

    # Receipts created from banking
    cur.execute('SELECT COUNT(*) FROM receipts WHERE created_from_banking = true')
    created_from_banking = cur.fetchone()[0]
    print(f'Receipts created_from_banking: {created_from_banking:,}')

    # Receipts not linked to banking
    cur.execute('SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NULL')
    not_linked = cur.fetchone()[0]
    print(f'Receipts NOT linked to banking: {not_linked:,}')

    print('\n=== VERIFIED BANKING RECORDS ===\n')

    # Check what bank IDs exist
    cur.execute("""
        SELECT bank_id, COUNT(*) 
        FROM banking_transactions 
        WHERE bank_id IS NOT NULL
        GROUP BY bank_id
        ORDER BY bank_id
    """)
    print("Bank IDs in banking_transactions:")
    for row in cur.fetchall():
        print(f"  bank_id {row[0]}: {row[1]:,} records")

    # Scotia Bank verified (bank_id = 2)
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions 
        WHERE bank_id = 2 
        AND reconciliation_status = 'verified'
    """)
    scotia_verified = cur.fetchone()[0]
    print(f'\nScotia Bank (bank_id=2) verified records: {scotia_verified:,}')

    # CIBC verified (bank_id = 1, account ending in 1615)
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions 
        WHERE bank_id = 1 
        AND reconciliation_status = 'verified'
    """)
    cibc_verified = cur.fetchone()[0]
    print(f'CIBC (bank_id=1) verified records: {cibc_verified:,}')

    print('\n=== RECEIPTS FROM VERIFIED BANKING ===\n')

    # Receipts from Scotia verified
    cur.execute("""
        SELECT COUNT(*) FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.bank_id = 2 
        AND bt.reconciliation_status = 'verified'
    """)
    scotia_receipts = cur.fetchone()[0]
    print(f'Receipts from Scotia verified: {scotia_receipts:,}')

    # Receipts from CIBC verified
    cur.execute("""
        SELECT COUNT(*) FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.bank_id = 1 
        AND bt.reconciliation_status = 'verified'
    """)
    cibc_receipts = cur.fetchone()[0]
    print(f'Receipts from CIBC verified: {cibc_receipts:,}')

    total_verified_receipts = scotia_receipts + cibc_receipts
    expected_remaining = total_receipts - total_verified_receipts
    print(f'\nTotal verified receipts to delete: {total_verified_receipts:,}')
    print(f'Expected remaining after deletion: {expected_remaining:,}')

    # Check for the 8362 target
    print(f'\n{"="*60}')
    if expected_remaining == 8362:
        print('✅ PERFECT! Remaining count matches expected 8362')
    else:
        print(f'⚠️  WARNING: Expected 8362 but would have {expected_remaining:,}')
        print(f'   Difference: {expected_remaining - 8362:,}')
    
    print('\n=== BREAKDOWN BY YEAR ===\n')
    
    # Receipts by year from verified banking
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM bt.transaction_date) as year,
            bt.bank_id,
            CASE 
                WHEN bt.bank_id = 1 THEN 'CIBC'
                WHEN bt.bank_id = 2 THEN 'Scotia'
                ELSE 'Other'
            END as bank_name,
            COUNT(*) as receipt_count
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.reconciliation_status = 'verified'
        GROUP BY EXTRACT(YEAR FROM bt.transaction_date), bt.bank_id
        ORDER BY year, bt.bank_id
    """)
    
    print(f"{'Year':<8} {'Bank':<10} {'Receipts':>12}")
    print('-' * 35)
    for row in cur.fetchall():
        year, bank_id, bank_name, count = row
        print(f'{int(year) if year else "NULL":<8} {bank_name:<10} {count:>12,}')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
