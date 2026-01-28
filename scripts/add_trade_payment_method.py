#!/usr/bin/env python
"""
Add 'trade' as a valid payment_method option to the payments table constraint.
"""
import psycopg2
import argparse

parser = argparse.ArgumentParser(description='Add trade as payment method.')
parser.add_argument('--write', action='store_true', help='Apply change; default is dry-run.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('ADD "TRADE" AS VALID PAYMENT_METHOD')
print('='*100)

# Check current constraint
cur.execute("""
    SELECT constraint_name, check_clause 
    FROM information_schema.check_constraints 
    WHERE constraint_name = 'chk_payment_method'
      AND table_name = 'payments'
""")
current = cur.fetchall()

print('\nCurrent constraint:')
for c in current:
    print(f'  {c[0]}: {c[1]}')

print('\nWill add "trade" to allowed values: cash, check, credit_card, debit_card, bank_transfer, unknown, trade')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to modify constraint.')
    cur.close()
    conn.close()
    exit(0)

# Drop old constraint
print('\nDropping old constraint...')
cur.execute("ALTER TABLE payments DROP CONSTRAINT chk_payment_method")
print('✓ Dropped chk_payment_method')

# Add new constraint with 'trade' included
print('\nAdding new constraint with "trade"...')
cur.execute("""
    ALTER TABLE payments 
    ADD CONSTRAINT chk_payment_method 
    CHECK (payment_method IN ('cash', 'check', 'credit_card', 'debit_card', 'bank_transfer', 'unknown', 'trade'))
""")
print('✓ Added chk_payment_method with "trade" option')

conn.commit()

# Verify
cur.execute("""
    SELECT constraint_name, check_clause 
    FROM information_schema.check_constraints 
    WHERE constraint_name = 'chk_payment_method'
      AND table_name = 'payments'
""")
new_constraint = cur.fetchall()

print('\nNew constraint:')
for c in new_constraint:
    print(f'  {c[0]}: {c[1]}')

cur.close()
conn.close()
print('\nDone.')
