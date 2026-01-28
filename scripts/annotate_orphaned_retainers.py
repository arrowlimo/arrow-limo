#!/usr/bin/env python3
"""
Step 2: Annotate remaining 195 orphaned Square payments with verification date
This creates an audit trail showing these were verified as legitimate retainers
"""

import psycopg2
from datetime import datetime
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print('\n' + '='*100)
print('STEP 2: ANNOTATE ORPHANED RETAINERS WITH VERIFICATION')
print('='*100 + '\n')

# Get current orphaned count
cur.execute('''
    SELECT COUNT(*) as count,
           COALESCE(SUM(amount), 0) as total
    FROM payments
    WHERE reserve_number IS NULL
    AND payment_method = 'credit_card'
''')

before_count, before_amount = cur.fetchone()

print(f'BEFORE ANNOTATION:')
print(f'  Orphaned payments: {before_count}')
print(f'  Total amount: ${before_amount:,.2f}')
print()

# Create annotation text
verification_date = datetime.now().strftime('%Y-%m-%d')
annotation = f'[VERIFIED ORPHANED RETAINER {verification_date}]'

print(f'Adding annotation: {annotation}')
print()

# Update notes field with annotation (handle NULL notes)
cur.execute('''
    UPDATE payments
    SET notes = CASE 
                  WHEN notes IS NULL OR notes = '' THEN %s
                  ELSE CONCAT(notes, ' ', %s)
                END
    WHERE reserve_number IS NULL
    AND payment_method = 'credit_card'
''', (annotation, annotation))

updated = cur.rowcount
conn.commit()

print(f'✅ UPDATED: {updated} orphaned payment records')
print()

# Verify annotation
cur.execute('''
    SELECT COUNT(*) as count,
           COALESCE(SUM(amount), 0) as total
    FROM payments
    WHERE reserve_number IS NULL
    AND payment_method = 'credit_card'
    AND notes LIKE %s
''', (f'%{verification_date}%',))

verified_count, verified_amount = cur.fetchone()

print(f'AFTER ANNOTATION:')
print(f'  Annotated records: {verified_count}')
print(f'  Total amount: ${verified_amount:,.2f}')
print()

print('='*100)
if verified_count == before_count:
    print('STATUS: ✅ ANNOTATION COMPLETE - All orphaned retainers marked for audit trail')
else:
    print(f'WARNING: Only {verified_count} of {before_count} records were updated')
print('='*100 + '\n')

cur.close()
conn.close()
