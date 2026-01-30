#!/usr/bin/env python
"""
Fix charter 016771 - LMS input error where deposit was entered as $2,330.63 instead of $230.63
The correct deposit should be $230.63 which matches the amount owed.
"""
import psycopg2
import argparse

parser = argparse.ArgumentParser(description='Fix charter 016771 deposit error.')
parser.add_argument('--write', action='store_true', help='Apply fix; default is dry-run.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

reserve = '016771'

print('='*100)
print('FIX CHARTER 016771 - LMS DEPOSIT INPUT ERROR')
print('='*100)

# Check current state
cur.execute("""
    SELECT reserve_number, total_amount_due, paid_amount, balance
    FROM charters
    WHERE reserve_number = %s
""", (reserve,))
row = cur.fetchone()

if row:
    print(f'\nCurrent state:')
    print(f'  total_amount_due: ${row[1]}')
    print(f'  paid_amount: ${row[2]}')
    print(f'  balance: ${row[3]}')

# Check payments
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_method
    FROM payments
    WHERE reserve_number = %s
    ORDER BY payment_date
""", (reserve,))
payments = cur.fetchall()

print(f'\nPayments: {len(payments)} total')
for p in payments:
    print(f'  payment_id={p[0]}: ${p[1]} on {p[2]} via {p[3]}')

total_paid = sum(p[1] for p in payments)
print(f'  Total: ${total_paid}')

# The correct amount should be $230.63 (matching total_amount_due)
from decimal import Decimal
correct_paid = Decimal('230.63')
overpayment = total_paid - correct_paid

print(f'\nCorrection needed:')
print(f'  Current paid_amount: ${row[2]}')
print(f'  Correct paid_amount: ${correct_paid}')
print(f'  Overpayment to remove: ${overpayment}')
print(f'  New balance: $0.00 (paid in full)')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to apply fix.')
    cur.close()
    conn.close()
    exit(0)

# Create backup
print('\nCreating backup...')
from table_protection import create_backup_before_delete
backup = create_backup_before_delete(cur, 'charters', condition=f"reserve_number = '{reserve}'")
print(f'✓ Backup: {backup}')

# Update charter
cur.execute("""
    UPDATE charters
    SET paid_amount = %s,
        balance = 0.00,
        updated_at = CURRENT_TIMESTAMP
    WHERE reserve_number = %s
""", (correct_paid, reserve))

conn.commit()
print(f'\n✓ Fixed charter {reserve}')
print(f'  paid_amount: ${total_paid} → ${correct_paid}')
print(f'  balance: ${row[3]} → $0.00')

# Check remaining urgent credits
cur.execute("SELECT COUNT(*), SUM(balance) FROM charters WHERE balance < -2000")
urgent_count, urgent_total = cur.fetchone()
print(f'\nRemaining urgent credits (< -$2K): {urgent_count} charters, ${urgent_total or 0:,.2f}')

cur.close()
conn.close()
print('\nDone.')
