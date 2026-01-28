#!/usr/bin/env python3
"""
Check the reconciliation and verification system in the database.
Shows what fields exist and how Welcome Wagon NSF pattern is tracked.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    # Check what reconciliation/verification columns exist
    print('=' * 100)
    print('BANKING_TRANSACTIONS RECONCILIATION/VERIFICATION COLUMNS')
    print('=' * 100)
    cur.execute('''
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'banking_transactions'
        AND (column_name LIKE '%reconcil%' OR column_name LIKE '%verified%' 
             OR column_name LIKE '%locked%' OR column_name LIKE '%nsf%')
        ORDER BY ordinal_position
    ''')
    for row in cur.fetchall():
        print(f'{row[0]:35} {row[1]:20} {str(row[2])[:40]}')

    print()
    print('=' * 100)
    print('RECEIPTS RECONCILIATION/VERIFICATION COLUMNS')
    print('=' * 100)
    cur.execute('''
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'receipts'
        AND (column_name LIKE '%reconcil%' OR column_name LIKE '%verified%' 
             OR column_name LIKE '%locked%' OR column_name LIKE '%banking%')
        ORDER BY ordinal_position
    ''')
    for row in cur.fetchall():
        print(f'{row[0]:35} {row[1]:20} {str(row[2])[:40]}')

    print()
    print('=' * 100)
    print('WELCOME WAGON NSF EXAMPLE - RECONCILIATION STATUS')
    print('=' * 100)
    print()
    
    # Show the Welcome Wagon NSF pattern with reconciliation status
    cur.execute('''
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.credit_amount,
            bt.is_nsf_charge,
            bt.reconciliation_status,
            bt.verified,
            bt.locked,
            r.receipt_id,
            r.vendor_name,
            r.gross_amount
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.description ILIKE '%welcome wagon%'
        ORDER BY bt.transaction_date, bt.transaction_id
    ''')
    
    print(f"{'TxnID':<8} {'Date':<12} {'Description':<40} {'Debit':>10} {'Credit':>10} {'NSF':>5} {'Reconcile':<12} {'Ver':>4} {'Lock':>4} {'RcptID':<8} {'Receipt Vendor':<30}")
    print('=' * 150)
    
    for row in cur.fetchall():
        txn_id = row[0]
        date = str(row[1])
        desc = (row[2] or '')[:40]
        debit = float(row[3] or 0)
        credit = float(row[4] or 0)
        nsf = 'Y' if row[5] else ''
        recn = (row[6] or '')[:12]
        ver = 'Y' if row[7] else ''
        lock = 'Y' if row[8] else ''
        rcpt_id = str(row[9] or '')
        vendor = (row[10] or '')[:30]
        
        print(f"{txn_id:<8} {date:<12} {desc:<40} {debit:>10.2f} {credit:>10.2f} {nsf:>5} {recn:<12} {ver:>4} {lock:>4} {rcpt_id:<8} {vendor:<30}")
    
    print()
    print('=' * 100)
    print('NSF PATTERN EXPLANATION')
    print('=' * 100)
    print()
    print('For NSF (Non-Sufficient Funds) transactions, the system should:')
    print()
    print('1. NSF RETURN (credit) - Money came back when check bounced')
    print('   - Creates receipt showing reversal')
    print('   - Should be marked: is_nsf_charge=TRUE, reconciliation_status=matched')
    print('   - Description should say "NSF RETURN"')
    print()
    print('2. NSF FEE (small debit) - Bank charged fee for bounced check')
    print('   - Creates receipt for the fee expense')
    print('   - Should be marked: is_nsf_charge=TRUE, reconciliation_status=matched')
    print('   - Description should say "NSF FEE"')
    print('   - Receipt category should be "Banking Fees"')
    print()
    print('3. RE-PAYMENT (new debit) - Successful retry payment')
    print('   - Creates NEW receipt for the actual payment')
    print('   - Should be marked: reconciliation_status=matched')
    print('   - Linked to a receipt showing the successful payment')
    print()
    print('VERIFICATION WORKFLOW:')
    print('  verified=FALSE → Transaction needs CRA verification')
    print('  verified=TRUE  → Transaction verified and approved for tax purposes')
    print('  locked=TRUE    → Transaction locked, cannot be modified (CRA audit trail)')
    print()
    
    # Check if there's a verification workflow table
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND (table_name LIKE '%verif%' OR table_name LIKE '%audit%' OR table_name LIKE '%ledger%')
        ORDER BY table_name
    """)
    
    audit_tables = cur.fetchall()
    if audit_tables:
        print('=' * 100)
        print('AUDIT/VERIFICATION TABLES IN DATABASE')
        print('=' * 100)
        for row in audit_tables:
            print(f'  • {row[0]}')
    
    conn.close()


if __name__ == "__main__":
    main()
