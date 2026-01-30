#!/usr/bin/env python3
"""Execute cleanup of 7 near-duplicate payments (non-multi-charter)"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print('\n' + '='*100)
print('PHASE 2: DELETING NON-MULTI-CHARTER NEAR-DUPLICATES')
print('='*100 + '\n')

# These are the 7 near-duplicates with single charters on their dates
# (not legitimate multi-charter payments)
delete_ids = [24956, 25052, 25041, 24977, 25068, 24945, 24874]

# Get amount before deletion
id_list = ','.join(str(id) for id in delete_ids)
cur.execute(f'SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM payments WHERE payment_id IN ({id_list})')
before_count, before_amount = cur.fetchone()

print('BEFORE PHASE 2 CLEANUP:')
print(f'  Payments to delete: {before_count}')
print(f'  Amount to recover: ${before_amount:,.2f}')
print()

# Show which ones are being deleted
delete_details = [
    (24956, 1076.00, '2025-12-02'),
    (25052, 774.00, '2025-10-09'),
    (25041, 500.00, '2025-10-16'),
    (24977, 327.75, '2025-11-25'),
    (25068, 322.87, '2025-10-01'),
    (24945, 300.00, '2025-12-03'),
    (24874, 257.55, '2025-12-22'),
]

print('Payments being deleted:')
for pid, amt, date in delete_details:
    print(f'  {pid}: ${amt:10.2f} on {date}')
print()

# Execute the delete
cur.execute(f'DELETE FROM payments WHERE payment_id IN ({id_list})')
deleted = cur.rowcount
conn.commit()

print(f'✅ COMMITTED: {deleted} payments deleted')
print(f'✅ RECOVERED: ${before_amount:,.2f}')
print()

# Validate new state
cur.execute('''
    SELECT 
        COUNT(*) as total_payments,
        COALESCE(SUM(amount), 0) as total_amount,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as linked,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as orphaned
    FROM payments
    WHERE payment_method = 'credit_card'
''')

total, amount, linked, orphaned = cur.fetchone()

print('='*100)
print('POST-PHASE 2 STATE')
print('='*100 + '\n')
print('Square Payments (credit_card):')
print(f'  Total: {total} (was 258, deleted {deleted})')
print(f'  Amount: ${amount:,.2f} (recovered ${before_amount:,.2f})')
print(f'  Linked to charters: {linked}')
print(f'  Orphaned retainers: {orphaned}')
print()

# Get breakdown of orphaned
cur.execute('''
    SELECT 
        COUNT(*) as count,
        COALESCE(SUM(amount), 0) as total,
        COUNT(CASE WHEN (amount % 100 = 0 OR amount % 50 = 0) THEN 1 END) as round_amounts
    FROM payments
    WHERE reserve_number IS NULL
    AND payment_method = 'credit_card'
''')

orp_count, orp_amount, round_count = cur.fetchone()

print('Orphaned Retainer Breakdown:')
print(f'  Count: {orp_count}')
print(f'  Amount: ${orp_amount:,.2f}')
print(f'  Round amounts (retainers): {round_count} ({round_count/orp_count*100:.1f}%)')
print()

# Final reconciliation
cur.execute('''
    SELECT COALESCE(SUM(amount), 0) 
    FROM payments
    WHERE reserve_number IS NOT NULL
    AND payment_method = 'credit_card'
''')
linked_amount = cur.fetchone()[0]

print('='*100)
print('RECONCILIATION CHECK')
print('='*100 + '\n')
print(f'Linked to charters: ${linked_amount:,.2f} ({linked} payments)')
print(f'Orphaned retainers: ${orp_amount:,.2f} ({orp_count} payments)')
print(f'Total: ${linked_amount + orp_amount:,.2f}')
print()

if abs(amount - (linked_amount + orp_amount)) < 0.01:
    print('✅ RECONCILIATION VERIFIED: All amounts accounted for (zero variance)')
else:
    diff = amount - (linked_amount + orp_amount)
    print(f'⚠️ DISCREPANCY: ${diff:,.2f}')

print()

cur.close()
conn.close()
