#!/usr/bin/env python
"""
Remove ALL duplicate payments from 2025-07-24 batch import.
These are duplicates of earlier payments that were incorrectly re-imported.
"""
import psycopg2
import argparse

parser = argparse.ArgumentParser(description='Remove all 2025-07-24 duplicate payments.')
parser.add_argument('--write', action='store_true', help='Apply deletions; default is dry-run.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('REMOVE ALL 2025-07-24 DUPLICATE PAYMENTS')
print('='*100)

# Find all 2025-07-24 payments that match earlier payment amounts (duplicates)
cur.execute("""
    WITH jul24_payments AS (
        SELECT payment_id, reserve_number, amount
        FROM payments
        WHERE payment_date = '2025-07-24'
          AND reserve_number IS NOT NULL
    ),
    earlier_payments AS (
        SELECT reserve_number, amount
        FROM payments
        WHERE payment_date < '2025-07-24'
          AND reserve_number IS NOT NULL
    )
    SELECT DISTINCT j.payment_id, j.reserve_number, j.amount
    FROM jul24_payments j
    INNER JOIN earlier_payments e ON e.reserve_number = j.reserve_number
                                 AND e.amount = j.amount
    ORDER BY j.reserve_number, j.amount
""")
duplicates = cur.fetchall()

print(f'\nFound {len(duplicates)} duplicate payments from 2025-07-24')

# Calculate total
total_duplicate_amount = sum(d[2] for d in duplicates)
print(f'Total duplicate amount: ${total_duplicate_amount:,.2f}')

# Count affected reserves
affected_reserves = set(d[1] for d in duplicates)
print(f'Affecting {len(affected_reserves)} reserve numbers')

# Show first 10 examples
print('\nFirst 10 examples:')
for d in duplicates[:10]:
    print(f'  payment_id={d[0]}: reserve={d[1]}, amount=${d[2]}')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to delete all 2025-07-24 duplicates.')
    cur.close()
    conn.close()
    exit(0)

# Create backup
print('\nCreating backup...')
from table_protection import create_backup_before_delete
payment_ids = ','.join(str(d[0]) for d in duplicates)
backup_name = create_backup_before_delete(cur, 'payments', 
                                          condition=f"payment_id IN ({payment_ids})")
print(f'✓ Backup: {backup_name}')

# Delete from income_ledger first (foreign key)
print('\nDeleting from income_ledger...')
cur.execute(f"""
    DELETE FROM income_ledger
    WHERE payment_id IN ({payment_ids})
""")
ledger_deleted = cur.rowcount
print(f'✓ Deleted {ledger_deleted} income_ledger rows')

# Delete payments
print('\nDeleting duplicate payments...')
cur.execute(f"""
    DELETE FROM payments
    WHERE payment_id IN ({payment_ids})
""")
deleted = cur.rowcount
print(f'✓ Deleted {deleted} payments')

conn.commit()

# Recalculate paid_amount for all affected charters
print(f'\nRecalculating paid_amount for {len(affected_reserves)} charters...')
recalc_count = 0
for reserve in sorted(affected_reserves):
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
    
    recalc_count += 1
    if recalc_count % 100 == 0:
        print(f'  Recalculated {recalc_count}/{len(affected_reserves)}...')

conn.commit()
print(f'✓ Recalculated {recalc_count} charters')

# Check remaining urgent credits
cur.execute("SELECT COUNT(*), SUM(balance) FROM charters WHERE balance < -2000")
urgent_count, urgent_total = cur.fetchone()
print(f'\nRemaining urgent credits (< -$2K): {urgent_count} charters, ${urgent_total or 0:,.2f}')

# Check overall balance status
cur.execute("""
    SELECT 
        COUNT(*) as charters,
        SUM(CASE WHEN balance < 0 THEN 1 ELSE 0 END) as credits,
        SUM(CASE WHEN balance < 0 THEN balance ELSE 0 END) as credit_total
    FROM charters
    WHERE total_amount_due > 0
""")
stats = cur.fetchone()
print(f'\nOverall status:')
print(f'  Total charters with charges: {stats[0]}')
print(f'  Charters with credits: {stats[1]}')
print(f'  Total credits: ${stats[2] or 0:,.2f}')

cur.close()
conn.close()
print('\nDone.')
