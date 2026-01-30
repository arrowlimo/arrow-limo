import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== STEP 1: Check what we already voided ===\n')
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, is_voided
    FROM receipts 
    WHERE receipt_id = 138832
""")
r = cur.fetchone()
if r:
    print(f'Receipt 138832: {r[1]} - ${r[2]:.2f} - Banking ID: {r[3]} - Voided: {r[4]}')

print('\n=== STEP 2: Find ALL receipts linked to bogus banking transaction 82299 ===\n')
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, banking_transaction_id, is_voided, exclude_from_reports
    FROM receipts 
    WHERE banking_transaction_id = 82299
    ORDER BY receipt_id
""")
receipts_from_bogus = cur.fetchall()
print(f'Total receipts linked to banking 82299: {len(receipts_from_bogus)}\n')
for r in receipts_from_bogus:
    voided = 'YES' if r[4] else 'NO'
    excluded = 'YES' if r[5] else 'NO'
    print(f'  Receipt {r[0]}: {r[1][:40]:40} ${r[2]:8.2f} | Voided:{voided} | Excluded:{excluded}')

print('\n=== STEP 3: Void ALL receipts from banking transaction 82299 ===\n')
cur.execute("""
    UPDATE receipts 
    SET is_voided = TRUE,
        exclude_from_reports = TRUE,
        potential_duplicate = TRUE,
        description = COALESCE(description, '') || ' [BOGUS JOURNAL ENTRY - VOIDED]'
    WHERE banking_transaction_id = 82299
      AND (is_voided IS NULL OR is_voided = FALSE)
""")
rows_voided = cur.rowcount
conn.commit()
print(f'✅ Voided {rows_voided} receipts from bogus banking transaction 82299')

print('\n=== STEP 4: Also void the banking transaction itself ===\n')
cur.execute("""
    UPDATE banking_transactions
    SET reconciliation_status = 'void',
        reconciliation_notes = COALESCE(reconciliation_notes, '') || ' [DUPLICATE JOURNAL ENTRY - VOIDED]'
    WHERE transaction_id = 82299
""")
conn.commit()
print(f'✅ Marked banking transaction 82299 as void')

print('\n=== STEP 5: Check for OTHER journal entry duplicates ===\n')
print('Looking for journal entries (account 1615) that match real bank transactions...\n')

cur.execute("""
    WITH journal_entries AS (
        SELECT bt.transaction_id, bt.transaction_date, bt.description, 
               bt.debit_amount, bt.credit_amount, r.receipt_id
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.account_number = '1615'
          AND bt.transaction_id != 82299
          AND (r.is_voided IS NULL OR r.is_voided = FALSE)
    ),
    real_bank_transactions AS (
        SELECT bt.transaction_id, bt.transaction_date, bt.description,
               bt.debit_amount, bt.credit_amount, bt.bank_id,
               r.receipt_id
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.bank_id IN (1, 2)  -- CIBC or Scotia only
          AND (r.is_voided IS NULL OR r.is_voided = FALSE)
    )
    SELECT 
        je.transaction_id as journal_txn,
        je.transaction_date,
        je.description as journal_desc,
        COALESCE(je.debit_amount, -je.credit_amount) as journal_amt,
        je.receipt_id as journal_receipt,
        rb.transaction_id as real_bank_txn,
        rb.description as real_desc,
        COALESCE(rb.debit_amount, -rb.credit_amount) as real_amt,
        rb.receipt_id as real_receipt,
        rb.bank_id
    FROM journal_entries je
    JOIN real_bank_transactions rb ON 
        je.transaction_date = rb.transaction_date
        AND ABS(COALESCE(je.debit_amount, -je.credit_amount) - COALESCE(rb.debit_amount, -rb.credit_amount)) < 0.01
    ORDER BY je.transaction_date, je.transaction_id
    LIMIT 50
""")
duplicates = cur.fetchall()

if duplicates:
    print(f'⚠️  Found {len(duplicates)} potential journal entry duplicates:\n')
    for d in duplicates:
        bank_name = "CIBC" if d[9] == 1 else "Scotia" if d[9] == 2 else "Other"
        print(f'{d[1]} | ${d[3]:8.2f} | Journal:{d[0]} (receipt {d[4]}) | {bank_name}:{d[5]} (receipt {d[8]})')
        print(f'  Journal: {d[2][:60]}')
        print(f'  Real:    {d[6][:60]}')
        print()
else:
    print('✅ No obvious journal entry duplicates found')

conn.close()
