"""Analyze current state of receipts and banking data for reconciliation."""
import psycopg2
import os
from datetime import datetime

def main():
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )
    cur = conn.cursor()

    # Get receipts table structure
    print('=== RECEIPTS TABLE COLUMNS ===')
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'receipts'
        ORDER BY ordinal_position
    """)
    for row in cur.fetchall():
        max_len = f'({row[2]})' if row[2] else ''
        print(f'{row[0]:35} {row[1]}{max_len:20} null={row[3]}')

    # Get count of receipts with various flags
    print('\n=== RECEIPTS STATUS ===')
    cur.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COUNT(banking_transaction_id) as linked_to_banking,
            COUNT(CASE WHEN created_from_banking = true THEN 1 END) as auto_created,
            COUNT(CASE WHEN is_personal_purchase = true THEN 1 END) as marked_personal,
            COUNT(CASE WHEN parent_receipt_id IS NOT NULL THEN 1 END) as split_children,
            COUNT(DISTINCT parent_receipt_id) as split_parents,
            COUNT(vehicle_id) as has_vehicle,
            COUNT(card_number) as has_card_number,
            COUNT(fuel_amount) as has_fuel_amount,
            COUNT(CASE WHEN business_personal = 'personal' THEN 1 END) as business_personal_flag
        FROM receipts
    """)
    row = cur.fetchone()
    if row[0] > 0:
        print(f'Total receipts: {row[0]:,}')
        print(f'Linked to banking: {row[1]:,} ({row[1]/row[0]*100:.1f}%)')
        print(f'Auto-created from banking: {row[2]:,}')
        print(f'Personal purchases: {row[3]:,}')
        print(f'Split children: {row[4]:,}')
        print(f'Split parents: {row[5]:,}')
        print(f'Has vehicle: {row[6]:,}')
        print(f'Has card number: {row[7]:,}')
        print(f'Has fuel amount: {row[8]:,}')
        print(f'Business/Personal flag: {row[9]:,}')
    
    # Get unlinked receipts by year
    print('\n=== UNLINKED RECEIPTS BY YEAR ===')
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as unlinked_count,
            SUM(gross_amount) as total_amount
        FROM receipts
        WHERE banking_transaction_id IS NULL
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    for row in cur.fetchall():
        if row[0]:
            print(f'{int(row[0])}: {row[1]:,} receipts, ${row[2]:,.2f}')

    # Get banking transactions count
    print('\n=== BANKING TRANSACTIONS ===')
    cur.execute("""
        SELECT 
            COUNT(*) as total_transactions,
            MIN(transaction_date) as earliest_date,
            MAX(transaction_date) as latest_date,
            COUNT(DISTINCT EXTRACT(YEAR FROM transaction_date)) as num_years,
            COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debits,
            COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credits
        FROM banking_transactions
    """)
    row = cur.fetchone()
    print(f'Total banking transactions: {row[0]:,}')
    print(f'Date range: {row[1]} to {row[2]}')
    print(f'Years covered: {row[3]}')
    print(f'Debits (expenses): {row[4]:,}')
    print(f'Credits (income): {row[5]:,}')

    # Unmatched banking transactions
    print('\n=== UNMATCHED BANKING DEBITS (EXPENSES) ===')
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as unmatched_count,
            SUM(debit_amount) as total_amount
        FROM banking_transactions bt
        WHERE debit_amount > 0
        AND NOT EXISTS (
            SELECT 1 FROM receipts r 
            WHERE r.banking_transaction_id = bt.transaction_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM banking_receipt_matching_ledger brl
            WHERE brl.banking_transaction_id = bt.transaction_id
        )
        GROUP BY EXTRACT(YEAR FROM transaction_date)
        ORDER BY year
    """)
    for row in cur.fetchall():
        if row[0]:
            print(f'{int(row[0])}: {row[1]:,} transactions, ${row[2]:,.2f}')

    # Check for banking_receipt_matching_ledger
    print('\n=== MATCHING LEDGER ===')
    cur.execute("""
        SELECT COUNT(*) FROM banking_receipt_matching_ledger
    """)
    ledger_count = cur.fetchone()[0]
    print(f'Banking-receipt ledger entries: {ledger_count:,}')

    # Potential duplicates
    print('\n=== POTENTIAL DUPLICATE RECEIPTS ===')
    cur.execute("""
        SELECT 
            COUNT(*) as duplicate_groups,
            SUM(cnt) as total_duplicates
        FROM (
            SELECT COUNT(*) as cnt
            FROM receipts
            WHERE receipt_date IS NOT NULL
            AND gross_amount IS NOT NULL
            AND vendor_name IS NOT NULL
            GROUP BY receipt_date, gross_amount, vendor_name
            HAVING COUNT(*) > 1
        ) dup
    """)
    row = cur.fetchone()
    print(f'Duplicate groups: {row[0]:,}')
    print(f'Total duplicate receipts: {row[1]:,}')

    # Banking accounts
    print('\n=== BANKING ACCOUNTS ===')
    try:
        cur.execute("""
            SELECT 
                ba.account_id,
                ba.account_name,
                ba.institution,
                ba.account_number,
                COUNT(bt.transaction_id) as txn_count,
                MIN(bt.transaction_date) as earliest,
                MAX(bt.transaction_date) as latest
            FROM bank_accounts ba
            LEFT JOIN banking_transactions bt ON bt.bank_id = ba.account_id
            GROUP BY ba.account_id, ba.account_name, ba.institution, ba.account_number
            ORDER BY ba.account_id
        """)
        for row in cur.fetchall():
            print(f'\n{row[1]} ({row[2]})')
            print(f'  Account #: {row[3]}')
            print(f'  Transactions: {row[4]:,}')
            if row[5]:
                print(f'  Date range: {row[5]} to {row[6]}')
    except Exception as e:
        print(f'Banking accounts info not available: {e}')

    print('\n=== ANALYSIS COMPLETE ===')

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
