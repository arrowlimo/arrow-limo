import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=== DELETING VOIDED JOURNAL ENTRY RECEIPTS AND TRANSACTIONS ===\n')

print('Step 1: Check payments linked to voided journal transactions...\n')
cur.execute("""
    SELECT COUNT(*)
    FROM payments p
    JOIN banking_transactions bt ON p.banking_transaction_id = bt.transaction_id
    WHERE bt.account_number = '1615'
      AND bt.reconciliation_status = 'void'
""")
payment_count = cur.fetchone()[0]
print(f'Payments linked to voided journal transactions: {payment_count}\n')

if payment_count > 0:
    print('Step 2: Unlink payments from voided journal banking transactions...')
    cur.execute("""
        UPDATE payments
        SET banking_transaction_id = NULL
        WHERE banking_transaction_id IN (
            SELECT transaction_id 
            FROM banking_transactions
            WHERE account_number = '1615'
              AND reconciliation_status = 'void'
        )
    """)
    unlinked_payments = cur.rowcount
    conn.commit()
    print(f'✅ Unlinked {unlinked_payments} payments\n')

print('Step 2b: Unlink cheque_register from voided journal banking transactions...')
cur.execute("""
    UPDATE cheque_register
    SET banking_transaction_id = NULL
    WHERE banking_transaction_id IN (
        SELECT transaction_id 
        FROM banking_transactions
        WHERE account_number = '1615'
          AND reconciliation_status = 'void'
    )
""")
unlinked_cheques = cur.rowcount
conn.commit()
print(f'✅ Unlinked {unlinked_cheques} cheque register entries\n')

print('Step 2c: Unlink any other banking_transactions references...')
cur.execute("""
    UPDATE banking_transactions
    SET receipt_id = NULL
    WHERE receipt_id IN (
        SELECT receipt_id 
        FROM receipts 
        WHERE is_voided = TRUE
          AND description LIKE '%JOURNAL ENTRY%'
    )
""")
unlinked_bt = cur.rowcount
conn.commit()
print(f'✅ Unlinked {unlinked_bt} banking transaction receipt references\n')

print('Step 3: Delete voided journal banking transactions...\n')
cur.execute("""
    DELETE FROM banking_transactions
    WHERE account_number = '1615'
      AND reconciliation_status = 'void'
      AND reconciliation_notes LIKE '%DUPLICATE%'
""")
deleted_banking = cur.rowcount
conn.commit()
print(f'✅ Deleted {deleted_banking} voided journal banking transactions\n')

print('Step 4: Delete voided journal entry receipts...\n')
cur.execute("""
    DELETE FROM receipts
    WHERE is_voided = TRUE
      AND description LIKE '%JOURNAL ENTRY%'
""")
deleted_receipts = cur.rowcount
conn.commit()
print(f'✅ Deleted {deleted_receipts} voided journal entry receipts\n')

print('Step 5: Verify cleanup...\n')
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE is_voided = TRUE 
      AND description LIKE '%JOURNAL ENTRY%'
""")
remaining_receipts = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE account_number = '1615'
      AND reconciliation_status = 'void'
""")
remaining_banking = cur.fetchone()[0]

print(f'Remaining voided journal receipts: {remaining_receipts}')
print(f'Remaining voided journal banking transactions: {remaining_banking}\n')

print('=== DELETION SUMMARY ===')
print(f'Payments unlinked: {unlinked_payments if payment_count > 0 else 0}')
print(f'Cheque register entries unlinked: {unlinked_cheques}')
print(f'Banking transactions unlinked: {unlinked_bt}')
print(f'Journal banking transactions deleted: {deleted_banking}')
print(f'Receipts deleted: {deleted_receipts}')
print('\n✅ Complete! All bogus journal entry duplicates have been removed.')
print('Note: Payments/cheques remain but are no longer linked to duplicate journal entries.')

conn.close()
