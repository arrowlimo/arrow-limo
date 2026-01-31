"""Analyze employee e-transfer data and its linkage to payroll/reimbursements."""

import psycopg2

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***',
    host='localhost'
)
cur = conn.cursor()

print('='*80)
print('EMPLOYEE E-TRANSFER ANALYSIS')
print('='*80)
print()

# Find all e-transfer transactions
print('1. E-Transfer Banking Transactions:')
print('-'*80)
cur.execute('''
    SELECT 
        account_number,
        COUNT(*) as count,
        SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
        SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits
    FROM banking_transactions
    WHERE LOWER(description) LIKE '%e-transfer%' OR LOWER(description) LIKE '%etransfer%'
    GROUP BY account_number
    ORDER BY account_number
''')
print(f"{'Account':<15s} {'Count':>6s} {'Debits':>15s} {'Credits':>15s}")
print('-'*80)
total_etransfers = 0
for row in cur.fetchall():
    acc, count, debits, credits = row
    total_etransfers += count
    print(f'{acc:<15s} {count:>6,} ${debits:>14,.2f} ${credits:>14,.2f}')
print(f"{'TOTAL':<15s} {total_etransfers:>6,}")
print()

# Check e-transfer connections to other tables
print('2. E-Transfer Linkage Status:')
print('-'*80)

# Count e-transfers linked to receipts
cur.execute('''
    SELECT COUNT(DISTINCT bt.transaction_id)
    FROM banking_transactions bt
    JOIN banking_receipt_matching_ledger bm ON bt.transaction_id = bm.banking_transaction_id
    WHERE LOWER(bt.description) LIKE '%e-transfer%' OR LOWER(bt.description) LIKE '%etransfer%'
''')
etransfer_to_receipts = cur.fetchone()[0]

# Count e-transfers linked to payments
cur.execute('''
    SELECT COUNT(DISTINCT p.banking_transaction_id)
    FROM payments p
    JOIN banking_transactions bt ON bt.transaction_id = p.banking_transaction_id
    WHERE LOWER(bt.description) LIKE '%e-transfer%' OR LOWER(bt.description) LIKE '%etransfer%'
''')
etransfer_to_payments = cur.fetchone()[0]

# Count e-transfers linked to email events
cur.execute('''
    SELECT COUNT(DISTINCT e.banking_transaction_id)
    FROM email_financial_events e
    JOIN banking_transactions bt ON bt.transaction_id = e.banking_transaction_id
    WHERE LOWER(bt.description) LIKE '%e-transfer%' OR LOWER(bt.description) LIKE '%etransfer%'
''')
etransfer_to_email = cur.fetchone()[0]

# Total unique e-transfers linked to something
cur.execute('''
    SELECT COUNT(DISTINCT bt.transaction_id)
    FROM banking_transactions bt
    WHERE (LOWER(bt.description) LIKE '%e-transfer%' OR LOWER(bt.description) LIKE '%etransfer%')
    AND (
        EXISTS (SELECT 1 FROM banking_receipt_matching_ledger bm WHERE bm.banking_transaction_id = bt.transaction_id)
        OR EXISTS (SELECT 1 FROM payments p WHERE p.banking_transaction_id = bt.transaction_id)
        OR EXISTS (SELECT 1 FROM email_financial_events e WHERE e.banking_transaction_id = bt.transaction_id)
    )
''')
total_linked = cur.fetchone()[0]
linked_pct = (total_linked / total_etransfers * 100) if total_etransfers > 0 else 0

print(f'E-Transfers linked to receipts:        {etransfer_to_receipts:6,}')
print(f'E-Transfers linked to payments:        {etransfer_to_payments:6,}')
print(f'E-Transfers linked to email events:    {etransfer_to_email:6,}')
print(f'Total e-transfers linked (any):        {total_linked:6,} ({linked_pct:.1f}%)')
print(f'Unlinked e-transfers:                  {total_etransfers - total_linked:6,}')
print()

# Get employee names from banking e-transfer descriptions
print('3. E-Transfer Direction:')
print('-'*80)
cur.execute('''
    SELECT 
        CASE 
            WHEN debit_amount > 0 THEN 'SENT (to employees)'
            ELSE 'RECEIVED (from customers)'
        END as direction,
        COUNT(*) as count,
        SUM(COALESCE(debit_amount, credit_amount)) as total_amount
    FROM banking_transactions
    WHERE LOWER(description) LIKE '%e-transfer%' OR LOWER(description) LIKE '%etransfer%'
    GROUP BY CASE WHEN debit_amount > 0 THEN 'SENT (to employees)' ELSE 'RECEIVED (from customers)' END
''')
print(f"{'Direction':<30s} {'Count':>6s} {'Amount':>15s}")
print('-'*80)
for row in cur.fetchall():
    direction, count, amount = row
    print(f'{direction:<30s} {count:>6,} ${amount:>14,.2f}')
print()

# Sample SENT e-transfers (to employees)
print('4. Sample E-Transfers SENT (to employees - payroll/reimbursements):')
print('-'*80)
cur.execute('''
    SELECT 
        transaction_date,
        description,
        debit_amount,
        CASE 
            WHEN EXISTS (
                SELECT 1 FROM banking_receipt_matching_ledger bm 
                WHERE bm.banking_transaction_id = bt.transaction_id
            ) THEN 'Receipt'
            WHEN EXISTS (
                SELECT 1 FROM payments p 
                WHERE p.banking_transaction_id = bt.transaction_id
            ) THEN 'Payment'
            ELSE 'Unlinked'
        END as linked_to
    FROM banking_transactions bt
    WHERE (LOWER(description) LIKE '%e-transfer%' OR LOWER(description) LIKE '%etransfer%')
    AND debit_amount > 0
    ORDER BY debit_amount DESC
    LIMIT 20
''')
print(f"{'Date':<12s} {'Amount':>10s} {'Linked':>10s} {'Description':<50s}")
print('-'*80)
for row in cur.fetchall():
    date, desc, amount, linked = row
    print(f'{str(date):<12s} ${amount:>9,.2f} {linked:>10s} {desc[:50]:<50s}')
print()

# Check for specific employee names in e-transfer descriptions
print('5. Employee Names Found in E-Transfer Descriptions:')
print('-'*80)
cur.execute('''
    SELECT 
        DISTINCT 
        SUBSTRING(description FROM 'E-TRANSFER.*TO (.+?)( |$)') as employee_name,
        COUNT(*) as count,
        SUM(debit_amount) as total_sent
    FROM banking_transactions
    WHERE debit_amount > 0
    AND (LOWER(description) LIKE '%e-transfer%' OR LOWER(description) LIKE '%etransfer%')
    GROUP BY SUBSTRING(description FROM 'E-TRANSFER.*TO (.+?)( |$)')
    ORDER BY count DESC
    LIMIT 20
''')
print(f"{'Employee Name':<30s} {'Count':>6s} {'Total Sent':>15s}")
print('-'*80)
for row in cur.fetchall():
    name, count, amount = row
    if name:
        print(f'{name[:30]:<30s} {count:>6,} ${amount:>14,.2f}')
print()

# Check payroll table for e-transfer payment method
print('6. Payroll Records Mentioning E-Transfer:')
print('-'*80)
cur.execute('''
    SELECT COUNT(*)
    FROM driver_payroll
    WHERE LOWER(COALESCE(notes, '')) LIKE '%e-transfer%' 
       OR LOWER(COALESCE(notes, '')) LIKE '%etransfer%'
       OR LOWER(COALESCE(source, '')) LIKE '%e-transfer%' 
       OR LOWER(COALESCE(source, '')) LIKE '%etransfer%'
''')
payroll_mentions = cur.fetchone()[0]
print(f'Driver payroll records with e-transfer mentions: {payroll_mentions:,}')

# Check if there are payment method fields
cur.execute('''
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'driver_payroll' 
    AND (column_name LIKE '%method%' OR column_name LIKE '%type%')
''')
method_cols = [row[0] for row in cur.fetchall()]
if method_cols:
    print(f'Payment method columns found: {", ".join(method_cols)}')
else:
    print('No payment method column found in driver_payroll')

print()
print('='*80)
print('SUMMARY')
print('='*80)
print(f'Total e-transfer transactions:  {total_etransfers:,}')
print(f'Linked to business records:     {total_linked:,} ({linked_pct:.1f}%)')
print(f'Unlinked (need investigation): {total_etransfers - total_linked:,}')
print()
print('NEXT STEPS:')
print('- Unlinked e-transfers may be employee payroll/reimbursements')
print('- Need to add payment_method field to driver_payroll table')
print('- Need to link e-transfer banking transactions to driver_payroll records')
print('- Extract employee names from e-transfer descriptions')
print('='*80)

cur.close()
conn.close()
