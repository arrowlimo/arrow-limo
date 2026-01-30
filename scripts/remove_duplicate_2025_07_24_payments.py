#!/usr/bin/env python
"""
Remove duplicate payments from 2025-07-24 bulk import that are causing false credits.
"""
import psycopg2
import argparse

parser = argparse.ArgumentParser(description='Remove duplicate 2025-07-24 payments.')
parser.add_argument('--write', action='store_true', help='Apply deletions; default is dry-run.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Specific duplicate payment_ids identified
duplicate_payment_ids = [
    20961,  # 017328: duplicate of 22626 ($3,805)
    16390,  # 014089: duplicate of 16811 ($3,240.80)
    16388,  # 014147: duplicate of 16809 ($1,740)
    16393,  # 014147: duplicate of 16814 ($469.24)
    5398,   # 003708: duplicate of 5240 ($2,340)
    12276,  # 010999: duplicate of 12586 ($2,016)
]

print('='*100)
print('REMOVE DUPLICATE 2025-07-24 PAYMENTS')
print('='*100)

# Get details before deletion
for payment_id in duplicate_payment_ids:
    cur.execute("""
        SELECT payment_id, reserve_number, amount, payment_date
        FROM payments
        WHERE payment_id = %s
    """, (payment_id,))
    row = cur.fetchone()
    if row:
        print(f'\nPayment {payment_id}: reserve={row[1]}, amount=${row[2]}, date={row[3]}')

total_to_remove = sum([3805, 3240.80, 1740, 469.24, 2340, 2016])
print(f'\nTotal amount to remove: ${total_to_remove:,.2f}')
print(f'Number of payments to delete: {len(duplicate_payment_ids)}')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to delete duplicates.')
    cur.close()
    conn.close()
    exit(0)

# Create backup
print('\nCreating backup...')
from table_protection import create_backup_before_delete
payment_list = ','.join(str(p) for p in duplicate_payment_ids)
backup_name = create_backup_before_delete(cur, 'payments', 
                                          condition=f"payment_id IN ({payment_list})")
print(f'✓ Backup: {backup_name}')

# Delete from income_ledger first (foreign key constraint)
print('\nDeleting from income_ledger...')
cur.execute(f"""
    DELETE FROM income_ledger
    WHERE payment_id IN ({payment_list})
""")
ledger_deleted = cur.rowcount
print(f'✓ Deleted {ledger_deleted} income_ledger rows')

# Delete payments
print('\nDeleting duplicate payments...')
cur.execute(f"""
    DELETE FROM payments
    WHERE payment_id IN ({payment_list})
""")
deleted = cur.rowcount
conn.commit()
print(f'✓ Deleted {deleted} payments')

# Recalculate paid_amount for affected charters
print('\nRecalculating paid_amount for affected charters...')
affected_reserves = ['017328', '014089', '014147', '003708', '010999']

for reserve in affected_reserves:
    # Sum from payments.reserve_number
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM payments
        WHERE reserve_number = %s
    """, (reserve,))
    new_paid = cur.fetchone()[0]
    
    # Update charter
    cur.execute("""
        UPDATE charters
        SET paid_amount = %s,
            balance = total_amount_due - %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE reserve_number = %s
    """, (new_paid, new_paid, reserve))
    
    print(f'  {reserve}: paid_amount updated to ${new_paid}')

conn.commit()

# Check remaining urgent credits
cur.execute("SELECT COUNT(*), SUM(balance) FROM charters WHERE balance < -2000")
urgent_count, urgent_total = cur.fetchone()
print(f'\nRemaining urgent credits (< -$2K): {urgent_count} charters, ${urgent_total or 0:,.2f}')

cur.close()
conn.close()
print('\nDone.')
