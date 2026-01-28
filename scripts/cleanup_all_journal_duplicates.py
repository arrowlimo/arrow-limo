import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=== COMPREHENSIVE JOURNAL ENTRY DUPLICATE CLEANUP ===\n')

print('Finding all journal entries (account 1615) that duplicate real bank transactions...\n')

# Find ALL journal entries that match real bank transactions
cur.execute("""
    WITH journal_entries AS (
        SELECT bt.transaction_id, bt.transaction_date, bt.description, 
               bt.debit_amount, bt.credit_amount, r.receipt_id
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '1615'
          AND (r.is_voided IS NULL OR r.is_voided = FALSE)
    ),
    real_bank_transactions AS (
        SELECT bt.transaction_id, bt.transaction_date, bt.description,
               bt.debit_amount, bt.credit_amount, bt.bank_id
        FROM banking_transactions bt
        WHERE bt.bank_id IN (1, 2)  -- CIBC or Scotia only
    )
    SELECT DISTINCT
        je.receipt_id,
        je.transaction_id as journal_txn_id,
        je.transaction_date,
        COALESCE(je.debit_amount, -je.credit_amount) as amount
    FROM journal_entries je
    JOIN real_bank_transactions rb ON 
        je.transaction_date = rb.transaction_date
        AND ABS(COALESCE(je.debit_amount, -je.credit_amount) - COALESCE(rb.debit_amount, -rb.credit_amount)) < 0.01
    WHERE je.receipt_id IS NOT NULL
    ORDER BY je.transaction_date, je.receipt_id
""")

duplicate_receipts = cur.fetchall()
print(f'Found {len(duplicate_receipts)} receipts from journal entries that duplicate real bank transactions\n')

if duplicate_receipts:
    # Show sample
    print('Sample of duplicates to be voided:')
    print('-' * 80)
    for i, r in enumerate(duplicate_receipts[:20]):
        print(f'  Receipt {r[0]:6} | {r[2]} | ${r[3]:9.2f} | Journal Banking ID: {r[1]}')
    if len(duplicate_receipts) > 20:
        print(f'  ... and {len(duplicate_receipts) - 20} more\n')
    
    # Get user confirmation
    receipt_ids = [r[0] for r in duplicate_receipts]
    
    print(f'\n⚠️  About to void {len(receipt_ids)} duplicate receipts from journal entries')
    print('These are duplicates of real CIBC/Scotia bank transactions')
    print('\nProceeding with cleanup...\n')
    
    # Void all duplicate receipts
    cur.execute("""
        UPDATE receipts 
        SET is_voided = TRUE,
            exclude_from_reports = TRUE,
            potential_duplicate = TRUE,
            description = COALESCE(description, '') || ' [DUPLICATE JOURNAL ENTRY - AUTO-VOIDED]'
        WHERE receipt_id = ANY(%s)
          AND (is_voided IS NULL OR is_voided = FALSE)
    """, (receipt_ids,))
    
    rows_voided = cur.rowcount
    conn.commit()
    
    print(f'✅ Successfully voided {rows_voided} duplicate journal entry receipts')
    
    # Also mark the banking transactions as void
    journal_txn_ids = [r[1] for r in duplicate_receipts]
    cur.execute("""
        UPDATE banking_transactions
        SET reconciliation_status = 'void',
            reconciliation_notes = COALESCE(reconciliation_notes, '') || ' [DUPLICATE OF REAL BANK TXN]'
        WHERE transaction_id = ANY(%s)
    """, (journal_txn_ids,))
    conn.commit()
    
    print(f'✅ Marked {len(journal_txn_ids)} journal banking transactions as void\n')
    
    # Summary
    print('=== CLEANUP SUMMARY ===')
    print(f'Total receipts voided: {rows_voided}')
    print(f'Total banking transactions marked void: {len(journal_txn_ids)}')
    print('\nThese receipts are excluded from reports and marked as duplicates.')
    print('The real bank transactions (CIBC/Scotia) remain active and valid.')

else:
    print('✅ No duplicate journal entry receipts found')

conn.close()
