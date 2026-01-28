#!/usr/bin/env python
"""
Bulk cleanup of cancelled charters with charges (pre-Oct 2025).
For each charter:
  - DELETE all charter_charges
  - UPDATE charters SET cancelled=TRUE, status='Cancelled', total_amount_due=0, balance=0
  - Backup before deletion
  - Audit logging
"""
import psycopg2
import argparse
import sys
sys.path.insert(0, 'l:/limo')
from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit

parser = argparse.ArgumentParser(description='Bulk cleanup cancelled charters with charges.')
parser.add_argument('--write', action='store_true', help='Apply changes; default is dry-run.')
parser.add_argument('--override-key', default='', help='Override key for protected deletion.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('Bulk Cleanup: Cancelled Charters with Charges (pre-Oct 2025)')
print('='*100)

# Find cancelled charters with charges
cur.execute("""
    SELECT DISTINCT
        c.reserve_number,
        c.charter_date,
        c.status,
        c.cancelled,
        c.total_amount_due,
        COUNT(cc.charge_id) as charge_count,
        COALESCE(SUM(cc.amount), 0) as total_charges
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.reserve_number = c.reserve_number
    WHERE (c.cancelled = TRUE OR c.status ILIKE '%cancel%')
      AND c.charter_date < '2025-10-01'
      AND (c.total_amount_due > 0 OR EXISTS (
          SELECT 1 FROM charter_charges WHERE reserve_number = c.reserve_number AND amount > 0
      ))
    GROUP BY c.reserve_number, c.charter_date, c.status, c.cancelled, c.total_amount_due
    ORDER BY c.charter_date DESC
""")
rows = cur.fetchall()

if not rows:
    print('\nNo cancelled charters with charges found.')
    cur.close()
    conn.close()
    exit(0)

print(f'\nTotal cancelled charters with charges: {len(rows)}')

total_charges = sum(r[6] for r in rows)
total_charge_rows = sum(r[5] for r in rows)
print(f'Total charge rows to delete: {total_charge_rows}')
print(f'Total charges amount: ${total_charges:,.2f}')

# Show top 20
print('\nTop 20 by charges amount:')
sorted_rows = sorted(rows, key=lambda r: r[6], reverse=True)
for r in sorted_rows[:20]:
    reserve_number, charter_date, status, cancelled, total_amount_due, charge_count, total_charges_amt = r
    print(f'  {reserve_number} date={charter_date} status={status} charges=${total_charges_amt} count={charge_count}')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write --override-key ALLOW_DELETE_CHARTER_CHARGES_20251110')
    cur.close()
    conn.close()
    exit(0)

# Protection check
try:
    protect_deletion('charter_charges', dry_run=False, override_key=args.override_key)
except Exception as e:
    print(f'\nProtection check failed: {e}')
    print('Provide --override-key ALLOW_DELETE_CHARTER_CHARGES_20251110')
    cur.close()
    conn.close()
    exit(1)

# Backup charter_charges
print('\nCreating charter_charges backup...')
reserve_list = ','.join(repr(r[0]) for r in rows)
backup_charges = create_backup_before_delete(cur, 'charter_charges', 
                                             condition=f"reserve_number IN ({reserve_list})")
print(f'✓ Backup: {backup_charges}')

# Backup charters
print('Creating charters backup...')
backup_charters = create_backup_before_delete(cur, 'charters', 
                                              condition=f"reserve_number IN ({reserve_list})")
print(f'✓ Backup: {backup_charters}')

# Process each charter
deleted_charge_count = 0
updated_charter_count = 0

for r in rows:
    reserve_number = r[0]
    
    # Delete charges
    cur.execute("DELETE FROM charter_charges WHERE reserve_number = %s", (reserve_number,))
    deleted_charge_count += cur.rowcount
    
    # Update charter
    cur.execute("""
        UPDATE charters
        SET cancelled = TRUE,
            status = 'Cancelled',
            total_amount_due = 0,
            balance = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE reserve_number = %s
    """, (reserve_number,))
    updated_charter_count += 1
    
    if updated_charter_count % 10 == 0:
        print(f'  Processed {updated_charter_count}/{len(rows)}...')

# Log audit
log_deletion_audit('charter_charges', deleted_charge_count, 
                   condition=f'reserve_number IN (cancelled charters pre-Oct 2025)')

conn.commit()

print(f'\n✓ Deleted {deleted_charge_count} charge rows')
print(f'✓ Updated {updated_charter_count} charters')
print(f'✓ Zeroed ${total_charges:,.2f} in charges')

# Verify
cur.execute("""
    SELECT COUNT(DISTINCT c.reserve_number)
    FROM charters c
    WHERE (c.cancelled = TRUE OR c.status ILIKE '%cancel%')
      AND c.charter_date < '2025-10-01'
      AND (c.total_amount_due > 0 OR EXISTS (
          SELECT 1 FROM charter_charges WHERE reserve_number = c.reserve_number AND amount > 0
      ))
""")
remaining = cur.fetchone()[0]
print(f'\nRemaining cancelled charters with charges: {remaining}')

cur.close()
conn.close()
print('\nDone.')
