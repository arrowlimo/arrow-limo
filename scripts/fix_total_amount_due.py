#!/usr/bin/env python
"""
Fix total_amount_due by recalculating from charter_charges sum.
This fixes the false credit issue where total_amount_due is incorrectly small.
"""
import psycopg2
import argparse

parser = argparse.ArgumentParser(description='Recalculate total_amount_due from charter_charges.')
parser.add_argument('--write', action='store_true', help='Apply corrections; default is dry-run.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('Recalculate total_amount_due from charter_charges')
print('='*100)

# Find charters where total_amount_due != SUM(charter_charges)
cur.execute("""
    WITH charge_sum AS (
        SELECT reserve_number, SUM(amount) as total_charges
        FROM charter_charges
        GROUP BY reserve_number
    )
    SELECT c.reserve_number,
           c.total_amount_due as current_total_due,
           cs.total_charges as calculated_total_due,
           c.paid_amount,
           c.balance as current_balance
    FROM charters c
    INNER JOIN charge_sum cs ON cs.reserve_number = c.reserve_number
    WHERE ABS(COALESCE(c.total_amount_due, 0) - cs.total_charges) > 0.01
      AND cs.total_charges > 0
    ORDER BY (COALESCE(c.total_amount_due, 0) - cs.total_charges) ASC
""")
discrepancies = cur.fetchall()

print(f'\nFound {len(discrepancies)} charters where total_amount_due != SUM(charter_charges)')

if not discrepancies:
    print('All charters have correct total_amount_due.')
    cur.close()
    conn.close()
    exit(0)

# Show top 20 largest discrepancies
print('\nTop 20 largest discrepancies (showing incorrect low totals):')
for r in discrepancies[:20]:
    reserve_number, current_total_due, calculated_total_due, paid_amount, current_balance = r
    diff = (current_total_due or 0) - calculated_total_due
    new_balance = calculated_total_due - (paid_amount or 0)
    print(f'  {reserve_number}:')
    print(f'    current_total_due=${current_total_due} -> should be ${calculated_total_due}')
    print(f'    current_balance=${current_balance} -> will be ${new_balance}')

total_adjustment = sum(r[2] - (r[1] or 0) for r in discrepancies)
print(f'\nTotal total_amount_due adjustment needed: ${total_adjustment:,.2f}')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to apply corrections.')
    cur.close()
    conn.close()
    exit(0)

# Create backup
print('\nCreating backup...')
from table_protection import create_backup_before_delete
reserve_list = ','.join(repr(r[0]) for r in discrepancies)
backup_name = create_backup_before_delete(cur, 'charters', 
                                          condition=f"reserve_number IN ({reserve_list})")
print(f'✓ Backup: {backup_name}')

# Apply corrections
print('\nApplying corrections...')
corrected_count = 0
for r in discrepancies:
    reserve_number, current_total_due, calculated_total_due, paid_amount, current_balance = r
    
    # Recalculate balance
    new_balance = calculated_total_due - (paid_amount or 0)
    
    cur.execute("""
        UPDATE charters
        SET total_amount_due = %s,
            balance = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE reserve_number = %s
    """, (calculated_total_due, new_balance, reserve_number))
    
    corrected_count += 1
    if corrected_count % 100 == 0:
        print(f'  Corrected {corrected_count}/{len(discrepancies)}...')

conn.commit()
print(f'\n✓ Corrected {corrected_count} charters')
print(f'✓ Adjusted total_amount_due by ${total_adjustment:,.2f}')

# Verify urgent credits are fixed
cur.execute("SELECT COUNT(*), SUM(balance) FROM charters WHERE balance < -2000")
urgent_count, urgent_total = cur.fetchone()
print(f'\nRemaining urgent credits (< -$2K): {urgent_count} charters, ${urgent_total or 0:,.2f}')

cur.close()
conn.close()
print('\nDone.')
