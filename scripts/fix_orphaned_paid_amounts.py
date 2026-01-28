#!/usr/bin/env python
"""
Fix orphaned paid_amount entries:
  - Charters have paid_amount > 0 but no payment linkages (no charter_payments, no payments.reserve_number)
  - Reset paid_amount = 0 and balance = total_amount_due (or 0 if null)
  - Log all changes for audit

SAFEGUARDS:
  - Exclude post-Oct 2025 charters
  - Backup before changes
  - Dry-run by default
"""
import psycopg2
import argparse
import sys
sys.path.insert(0, 'l:/limo')
from table_protection import create_backup_before_delete

parser = argparse.ArgumentParser(description='Fix orphaned paid_amount entries (no payment linkages).')
parser.add_argument('--write', action='store_true', help='Apply changes; default is dry-run.')
parser.add_argument('--limit', type=int, default=None, help='Limit number of charters to fix.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('Fix Orphaned paid_amount (no payment linkages)')
print('='*100)

# Find charters with orphaned paid_amount (excluding post-Oct 2025)
cur.execute("""
    SELECT c.reserve_number,
           c.charter_date,
           c.total_amount_due,
           c.paid_amount,
           c.balance
    FROM charters c
    WHERE c.paid_amount > 0
      AND c.charter_date < '2025-10-01'
      AND NOT EXISTS (
          SELECT 1 FROM charter_payments WHERE charter_id = c.reserve_number
      )
      AND NOT EXISTS (
          SELECT 1 FROM payments WHERE reserve_number = c.reserve_number
      )
    ORDER BY c.charter_date DESC
""")
rows = cur.fetchall()

if not rows:
    print('\nNo orphaned paid_amount found.')
    cur.close()
    conn.close()
    exit(0)

total_count = len(rows)
if args.limit:
    rows = rows[:args.limit]

print(f'\nTotal orphaned charters: {total_count}')
print(f'Processing: {len(rows)}')

total_paid_to_zero = sum(r[3] for r in rows)
print(f'Total paid_amount to be zeroed: ${total_paid_to_zero:,.2f}')

# Show sample
print('\nSample (first 10):')
for r in rows[:10]:
    reserve_number, charter_date, total_amount_due, paid_amount, balance = r
    print(f'  {reserve_number} date={charter_date} total_due={total_amount_due} paid=${paid_amount} balance={balance}')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to apply.')
    cur.close()
    conn.close()
    exit(0)

# Backup
print('\nCreating backup...')
reserve_list = ','.join(repr(r[0]) for r in rows)
backup_name = create_backup_before_delete(cur, 'charters', 
                                          condition=f"reserve_number IN ({reserve_list})")
print(f'Backup: {backup_name}')

# Fix each charter
fixed_count = 0
for r in rows:
    reserve_number, charter_date, total_amount_due, paid_amount, balance = r
    
    # Reset: paid_amount = 0, balance = total_amount_due (or 0 if null)
    new_balance = total_amount_due if total_amount_due else 0
    
    cur.execute("""
        UPDATE charters
        SET paid_amount = 0,
            balance = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE reserve_number = %s
    """, (new_balance, reserve_number))
    
    fixed_count += 1
    if fixed_count % 100 == 0:
        print(f'  Fixed {fixed_count}/{len(rows)}...')

conn.commit()
print(f'\n✓ Fixed {fixed_count} charters')
print(f'✓ Zeroed ${total_paid_to_zero:,.2f} orphaned paid_amount')

# Verify
cur.execute("""
    SELECT COUNT(*), SUM(paid_amount)
    FROM charters c
    WHERE c.paid_amount > 0
      AND c.charter_date < '2025-10-01'
      AND NOT EXISTS (SELECT 1 FROM charter_payments WHERE charter_id = c.reserve_number)
      AND NOT EXISTS (SELECT 1 FROM payments WHERE reserve_number = c.reserve_number)
""")
remaining_count, remaining_amount = cur.fetchone()
print(f'\nRemaining orphaned: {remaining_count} charters, ${remaining_amount or 0:,.2f}')

cur.close()
conn.close()
print('\nDone.')
