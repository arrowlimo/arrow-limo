#!/usr/bin/env python3
"""
Create test split receipts for UI testing
"""

import psycopg2
from datetime import date

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print('\n' + '='*80)
print('CREATE TEST SPLIT RECEIPTS FOR UI TESTING')
print('='*80)

try:
    # Create a test banking transaction
    cur.execute("""
        INSERT INTO banking_transactions 
        (transaction_date, description, debit, credit, balance, account_name, 
         bank_account_id, reconciliation_status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING transaction_id
    """, (date.today(), 'TEST SPLIT - 2000 payment', None, 2000.00, 0, 'CIBC 0228362', 1, 'unmatched'))
    txn_id = cur.fetchone()[0]
    conn.commit()
    print(f'\nCreated test banking transaction #{txn_id}: $2000')
    
    # Create 3 test receipts
    receipt_data = [
        ('Acme Corp', 1200.00, 'Part 1 of split'),
        ('Acme Corp', 500.00, 'Part 2 of split'),
        ('Acme Corp', 300.00, 'Part 3 of split'),
    ]
    
    receipt_ids = []
    for vendor, amount, desc in receipt_data:
        cur.execute("""
            INSERT INTO receipts 
            (receipt_date, vendor_name, gross_amount, payment_method, description,
             gl_account_code, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING receipt_id
        """, (date.today(), vendor, amount, 'check', desc, '4100'))
        rid = cur.fetchone()[0]
        receipt_ids.append(rid)
        print(f'  Created receipt #{rid}: {vendor} ${amount:,.2f}')
    
    conn.commit()
    
    # Link all 3 receipts to same banking transaction
    print(f'\nLinking all {len(receipt_ids)} receipts to transaction #{txn_id}:')
    for rid in receipt_ids:
        cur.execute("""
            INSERT INTO receipt_banking_links 
            (receipt_id, transaction_id, linked_amount, link_status, linked_by, linked_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (rid, txn_id, 2000.00 / len(receipt_ids), 'linked', 'test_script'))
        print(f'  Linked receipt #{rid}')
    
    # Update banking transaction with first receipt
    cur.execute("""
        UPDATE banking_transactions SET receipt_id = %s, reconciliation_status = 'matched'
        WHERE transaction_id = %s
    """, (receipt_ids[0], txn_id))
    
    conn.commit()
    
    print(f'\nREADY TO TEST:')
    print(f'   Transaction ID: {txn_id}')
    print(f'   Receipt IDs: {receipt_ids}')
    print(f'   Load any of these receipt IDs in the UI and it should show as split!')
    
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
    conn.rollback()

finally:
    cur.close()
    conn.close()

print('\n' + '='*80)
print('TEST DATA CREATED - Launch UI and test split detection')
print('='*80 + '\n')
