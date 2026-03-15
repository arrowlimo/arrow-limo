#!/usr/bin/env python
"""
Add 'trade_of_services' as a valid payment_method option.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('ADD TRADE_OF_SERVICES PAYMENT METHOD')
print('='*100)

# Drop existing constraint
print('\nDropping existing chk_payment_method constraint...')
cur.execute("""
    ALTER TABLE payments DROP CONSTRAINT IF EXISTS chk_payment_method
""")

# Add new constraint with trade_of_services
print('Adding new constraint with trade_of_services...')
cur.execute("""
    ALTER TABLE payments 
    ADD CONSTRAINT chk_payment_method 
    CHECK (payment_method IN (
        'cash', 
        'check', 
        'credit_card', 
        'debit_card', 
        'bank_transfer', 
        'trade_of_services', 
        'unknown'
    ))
""")

conn.commit()
print('\n✓ Added trade_of_services to valid payment methods')

# Verify
cur.execute("""
    SELECT constraint_name, check_clause 
    FROM information_schema.check_constraints 
    WHERE constraint_name = 'chk_payment_method'
""")
print('\nNew constraint:')
for row in cur.fetchall():
    print(f'  {row[0]}')
    print(f'  {row[1]}')

cur.close()
conn.close()
print('\nDone.')
