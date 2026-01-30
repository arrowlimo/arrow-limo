import psycopg2
import pyodbc
from datetime import timedelta

pg = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg.cursor()

lms = pyodbc.connect(r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\backups\lms.mdb;')
lms_cur = lms.cursor()

print("Finding correct reserve assignments for 20 misallocated $774 payments")
print("=" * 80)
print()

# Get the 20 NULL-key payments
pg_cur.execute('''
    SELECT payment_id, payment_date, amount
    FROM payments
    WHERE reserve_number = '013932'
    AND payment_key IS NULL
    ORDER BY payment_date
''')
misallocated_payments = pg_cur.fetchall()

# Get all Waste Connections $774 charters
pg_cur.execute('''
    SELECT reserve_number, charter_date, paid_amount, balance
    FROM charters
    WHERE client_id = 2311
    AND ABS(total_amount_due - 774.00) < 0.01
    ORDER BY charter_date
''')
all_charters = pg_cur.fetchall()

print(f"Matching {len(misallocated_payments)} payments to {len(all_charters)} charters...")
print()

proposals = []
for payment_id, payment_date, amount in misallocated_payments:
    # Find charter closest to payment date that needs payment
    best_match = None
    best_distance = None
    
    for reserve, charter_date, paid, balance in all_charters:
        # Skip if already fully paid or is 013932
        if balance <= 0 or reserve == '013932':
            continue
        
        days_diff = abs((charter_date - payment_date).days)
        if days_diff <= 180:  # Within 6 months
            if best_distance is None or days_diff < best_distance:
                best_distance = days_diff
                best_match = (reserve, charter_date, paid, balance)
    
    if best_match:
        target_reserve, charter_date, paid, balance = best_match
        proposals.append({
            'payment_id': payment_id,
            'payment_date': payment_date,
            'amount': float(amount),
            'from_reserve': '013932',
            'to_reserve': target_reserve,
            'charter_date': charter_date,
            'days_diff': best_distance,
            'current_paid': float(paid),
            'current_balance': float(balance),
        })
        print(f"Payment {payment_id} ({payment_date}) → Reserve {target_reserve} ({charter_date}, {best_distance} days)")
    else:
        print(f"Payment {payment_id} ({payment_date}) → NO MATCH FOUND")

print()
print(f"Successfully matched {len(proposals)} of {len(misallocated_payments)} payments")
print()

if len(proposals) == len(misallocated_payments):
    print("✓ All payments can be reallocated to unpaid charters")
    print()
    print("To fix:")
    print("  1. Update payments.reserve_number for these 20 payments")
    print("  2. Recalculate charter.paid_amount for affected reserves")
    print("  3. Remove or reduce credit from 013932")
else:
    print(f"⚠ {len(misallocated_payments) - len(proposals)} payments cannot be matched")
