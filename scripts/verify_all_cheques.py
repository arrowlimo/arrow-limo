"""
Verify all cheque transactions (read-only, no modifications to locked 2012 data).
"""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print('=' * 120)
print('ALL CHEQUE TRANSACTION VERIFICATION (INCLUDING NSF)')
print('=' * 120)

# Get all cheque transactions
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        CASE 
            WHEN bt.bank_id = 1 THEN 'CIBC'
            WHEN bt.bank_id = 2 THEN 'SCOTIA'
            ELSE 'Unknown'
        END as bank,
        bt.debit_amount,
        bt.credit_amount,
        bt.description,
        r.receipt_id,
        r.vendor_name,
        CASE 
            WHEN bt.description ILIKE '%NSF%' THEN 'NSF'
            WHEN bt.description ILIKE '%RETURN%' THEN 'RETURN'
            ELSE ''
        END as nsf_flag,
        bt.reconciliation_status
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.description ILIKE '%CHQ%' OR bt.description ILIKE '%CHEQUE%'
    ORDER BY bt.transaction_date, bt.transaction_id
""")

all_cheques = cur.fetchall()

# Categorize
debit_tx = [t for t in all_cheques if t[3]]
credit_tx = [t for t in all_cheques if t[4]]
has_receipt = [t for t in all_cheques if t[6]]
no_receipt = [t for t in all_cheques if not t[6]]
nsf_tx = [t for t in all_cheques if t[8]]
duplicates = [t for t in all_cheques if t[9] == 'DUPLICATE']

print(f'\nTotal cheque transactions: {len(all_cheques)}')
print(f'  DEBIT (actual cheques out): {len(debit_tx)}')
print(f'  CREDIT (QB journal entries): {len(credit_tx)}')
print(f'  With receipts: {len(has_receipt)}')
print(f'  Without receipts: {len(no_receipt)}')
print(f'  NSF/RETURN: {len(nsf_tx)}')
print(f'  Marked as DUPLICATE: {len(duplicates)}')

# Show debits without receipts (excluding NSF and duplicates)
debit_no_receipt = [t for t in debit_tx if not t[6] and not t[8] and t[9] != 'DUPLICATE']
print(f'\n\nDEBIT CHEQUES WITHOUT RECEIPTS (non-NSF, non-duplicate): {len(debit_no_receipt)}')
if debit_no_receipt:
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Amount':>10} | Description")
    print('-' * 100)
    for tx_id, date, bank, debit, credit, desc, receipt_id, vendor, nsf, recon in debit_no_receipt[:25]:
        print(f'{tx_id:6d} | {date} | {bank:7} | ${debit:>9,.2f} | {desc[:60]}')
    if len(debit_no_receipt) > 25:
        print(f'  ... and {len(debit_no_receipt) - 25} more')

# Show NSF transactions
if nsf_tx:
    print(f'\n\nNSF/RETURN TRANSACTIONS: {len(nsf_tx)}')
    print(f"{'TX':>6} | {'Date':10} | {'Bank':7} | {'Debit':>10} | {'Credit':>10} | {'Receipt':>8} | Description")
    print('-' * 110)
    for tx_id, date, bank, debit, credit, desc, receipt_id, vendor, nsf, recon in nsf_tx:
        debit_str = f'${debit:,.2f}' if debit else ''
        credit_str = f'${credit:,.2f}' if credit else ''
        receipt_str = str(receipt_id) if receipt_id else 'NONE'
        print(f'{tx_id:6d} | {date} | {bank:7} | {debit_str:>10} | {credit_str:>10} | {receipt_str:>8} | {desc[:50]}')

# Show duplicates
if duplicates:
    print(f'\n\nMARKED AS DUPLICATE: {len(duplicates)}')
    for tx_id, date, bank, debit, credit, desc, receipt_id, vendor, nsf, recon in duplicates:
        amount = debit if debit else credit
        print(f'  TX {tx_id:6d} | {date} | {bank:7} | ${amount:>9,.2f} | {desc[:60]}')

# Show CREDIT transactions (QB journal entries - these don't need receipts)
print(f'\n\nCREDIT TRANSACTIONS (QB journal entries, no receipts needed): {len(credit_tx)}')
if credit_tx:
    for tx_id, date, bank, debit, credit, desc, receipt_id, vendor, nsf, recon in credit_tx[:10]:
        receipt_str = str(receipt_id) if receipt_id else 'NONE'
        print(f'  TX {tx_id:6d} | {date} | {bank:7} | ${credit:>9,.2f} CREDIT | {receipt_str:>8} | {desc[:50]}')
    if len(credit_tx) > 10:
        print(f'  ... and {len(credit_tx) - 10} more')

print('\n✅ VERIFICATION COMPLETE')
print(f'\n⚠️  NOTE: TX 81373 is a duplicate of TX 56865 but cannot be marked (2012 is locked)')
print(f'    Receipt 139332 should be linked to TX 56865, currently linked to TX 81373')

cur.close()
conn.close()
