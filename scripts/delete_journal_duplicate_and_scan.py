import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('=== STEP 1: Remove duplicate journal entry receipt 138832 ===\n')

# First, verify what we're removing
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           banking_transaction_id, description
    FROM receipts 
    WHERE receipt_id = 138832
""")
r = cur.fetchone()
if r:
    print(f'Removing Receipt:')
    print(f'  ID: {r[0]}')
    print(f'  Date: {r[1]}')
    print(f'  Vendor: {r[2]}')
    print(f'  Amount: ${r[3]:.2f}')
    print(f'  Banking ID: {r[4]}')
    
    # First unlink the banking transaction
    cur.execute("""
        UPDATE banking_transactions 
        SET receipt_id = NULL 
        WHERE receipt_id = 138832
    """)
    print(f'\n  Unlinked from banking transaction {r[4]}')
    
    # Mark as duplicate/voided instead of deleting
    cur.execute("""
        UPDATE receipts 
        SET is_voided = TRUE,
            exclude_from_reports = TRUE,
            potential_duplicate = TRUE,
            description = COALESCE(description, '') || ' [DUPLICATE JOURNAL ENTRY - VOIDED]'
        WHERE receipt_id = 138832
    """)
    
    conn.commit()
    print(f'✅ VOIDED receipt 138832 (marked as duplicate journal entry)')
    print(f'   Rows affected: {cur.rowcount}')
else:
    print('Receipt 138832 not found')

print('\n=== STEP 2: Find other receipts from Account 1615 (journal entries) ===\n')

cur.execute("""
    SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount, 
           r.banking_transaction_id, bt.description, bt.account_number,
           r.is_voided, r.exclude_from_reports
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.account_number = '1615'
      AND (r.is_voided IS NULL OR r.is_voided = FALSE)
    ORDER BY r.receipt_date, r.receipt_id
""")
journal_receipts = cur.fetchall()

print(f'Total active receipts from Account 1615: {len(journal_receipts)}\n')

if journal_receipts:
    print('Receipt ID | Date       | Vendor                         | Amount    | Banking ID | Description')
    print('-' * 110)
    for r in journal_receipts:
        vendor = (r[2][:30] if r[2] else 'none').ljust(30)
        desc = (r[5][:40] if r[5] else 'none')
        banking_id = str(r[4]) if r[4] else 'none'
        print(f'{r[0]:10} | {r[1]} | {vendor} | ${r[3]:8.2f} | {banking_id:10} | {desc}')

    print('\n=== STEP 3: Check for potential duplicates ===\n')
    
    potential_duplicates = []
    
    for jr in journal_receipts:
        receipt_id = jr[0]
        receipt_date = jr[1]
        vendor = jr[2]
        amount = jr[3]
        
        # Look for matching receipts on same date with similar amount from real banks
        cur.execute("""
            SELECT r.receipt_id, r.vendor_name, r.gross_amount, 
                   bt.account_number, bt.description, bt.bank_id
            FROM receipts r
            JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
            WHERE r.receipt_date = %s
              AND ABS(r.gross_amount - %s) < 0.01
              AND r.receipt_id != %s
              AND bt.account_number != '1615'
              AND (r.is_voided IS NULL OR r.is_voided = FALSE)
            ORDER BY r.receipt_id
        """, (receipt_date, amount, receipt_id))
        
        matches = cur.fetchall()
        if matches:
            # Check if any match is from a real bank (CIBC or Scotia)
            real_bank_match = any(m[5] in (1, 2) for m in matches)
            if real_bank_match:
                potential_duplicates.append({
                    'journal_receipt': jr,
                    'matches': matches
                })
    
    if potential_duplicates:
        print(f'⚠️  Found {len(potential_duplicates)} potential duplicate situations:\n')
        for dup in potential_duplicates:
            jr = dup['journal_receipt']
            print(f'Journal Entry Receipt {jr[0]} ({jr[1]}) - {jr[2]} - ${jr[3]:.2f}')
            print(f'  Potential duplicates from real banks:')
            for match in dup['matches']:
                bank_name = "CIBC" if match[5] == 1 else "Scotia" if match[5] == 2 else "Other"
                print(f'    Receipt {match[0]}: {match[1]} - ${match[2]:.2f} - {bank_name} Acct {match[3]} - {match[4][:50]}')
            print()
    else:
        print('✅ No obvious duplicates found among remaining journal entries')

else:
    print('✅ No active receipts found from Account 1615')

conn.close()
