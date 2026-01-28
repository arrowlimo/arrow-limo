import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=== INVESTIGATING DELETION OF VOIDED JOURNAL ENTRY RECEIPTS ===\n')

# Check what's referencing the voided receipts
print('Step 1: Check foreign key constraints on receipts table...\n')
cur.execute("""
    SELECT
        tc.constraint_name,
        tc.table_name,
        kcu.column_name,
        ccu.table_name AS foreign_table_name,
        ccu.column_name AS foreign_column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND ccu.table_name = 'receipts'
""")
fk_constraints = cur.fetchall()
print(f'Found {len(fk_constraints)} tables referencing receipts:\n')
for fk in fk_constraints:
    print(f'  Table: {fk[1]:30} Column: {fk[2]:30} -> receipts.{fk[4]}')

print('\n\nStep 2: Count voided receipts and their banking transaction links...\n')
cur.execute("""
    SELECT COUNT(*), 
           COUNT(banking_transaction_id) as with_banking_link
    FROM receipts 
    WHERE is_voided = TRUE
      AND description LIKE '%JOURNAL ENTRY%'
""")
counts = cur.fetchone()
print(f'Total voided journal receipts: {counts[0]}')
print(f'With banking transaction link: {counts[1]}')

print('\n\nStep 3: Check if banking_transactions reference these receipts...\n')
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions bt
    JOIN receipts r ON bt.receipt_id = r.receipt_id
    WHERE r.is_voided = TRUE
      AND r.description LIKE '%JOURNAL ENTRY%'
""")
bt_refs = cur.fetchone()[0]
print(f'Banking transactions referencing voided receipts: {bt_refs}')

print('\n\nStep 4: Safe deletion strategy...\n')
print('To safely delete these voided receipts:')
print('1. First, unlink them from banking_transactions (set receipt_id = NULL)')
print('2. Then delete the receipts')
print('3. Optionally delete the voided journal banking transactions (account 1615)')

print('\n\nStep 5: Prepare deletion commands...\n')

# Get list of voided receipt IDs
cur.execute("""
    SELECT receipt_id 
    FROM receipts 
    WHERE is_voided = TRUE
      AND description LIKE '%JOURNAL ENTRY%'
    ORDER BY receipt_id
""")
voided_ids = [r[0] for r in cur.fetchall()]

print(f'Ready to delete {len(voided_ids)} voided journal entry receipts')
print(f'Sample receipt IDs: {voided_ids[:10]}...\n')

# Get list of voided banking transaction IDs
cur.execute("""
    SELECT transaction_id 
    FROM banking_transactions
    WHERE account_number = '1615'
      AND reconciliation_status = 'void'
    ORDER BY transaction_id
""")
voided_banking_ids = [r[0] for r in cur.fetchall()]
print(f'Ready to delete {len(voided_banking_ids)} voided journal banking transactions')
print(f'Sample banking IDs: {voided_banking_ids[:10]}...\n')

print('=== DELETION PLAN ===\n')
print('Execute in this order:')
print(f'1. Unlink banking_transactions.receipt_id for {bt_refs} transactions')
print(f'2. Delete {len(voided_ids)} voided receipts')
print(f'3. Delete {len(voided_banking_ids)} voided journal banking transactions')
print('\nProceed with deletion? (Next script will execute this)')

conn.close()
