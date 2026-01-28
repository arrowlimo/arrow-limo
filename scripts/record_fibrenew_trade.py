#!/usr/bin/env python
"""
Record trade of services for charters 017822 and 017823 (Fibrenew rent trade).
These charters were provided in exchange for Fibrenew rent owed, not cash payment.
Record as "Trade - Fibrenew Rent" payments to balance to $0.
"""
import psycopg2
import argparse
from decimal import Decimal

parser = argparse.ArgumentParser(description='Record Fibrenew rent trade for charters 017822/017823.')
parser.add_argument('--write', action='store_true', help='Apply changes; default is dry-run.')
args = parser.parse_args()

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print('='*100)
print('RECORD FIBRENEW RENT TRADE FOR CHARTERS 017822/017823')
print('='*100)

# Charter details
charters = ['017822', '017823']
trade_details = {}

for reserve in charters:
    cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    c = cur.fetchone()
    
    if c:
        print(f'\n{reserve}:')
        print(f'  Charter date: {c[1]}')
        print(f'  Total amount due: ${c[2]}')
        print(f'  Current paid amount: ${c[3]}')
        print(f'  Current balance: ${c[4]}')
        
        # Get existing payments
        cur.execute("""
            SELECT payment_id, amount, payment_date, payment_method
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date
        """, (reserve,))
        payments = cur.fetchall()
        
        print(f'  Existing payments: {len(payments)}')
        for p in payments:
            print(f'    ${p[1]} on {p[2]} via {p[3]}')
        
        # Calculate trade amount needed to balance to zero
        trade_amount = c[4]  # Current balance
        trade_details[reserve] = {
            'charter_date': c[1],
            'total_due': c[2],
            'current_paid': c[3],
            'balance': c[4],
            'trade_amount': trade_amount
        }
        
        print(f'  → Trade payment needed: ${trade_amount}')

total_trade = sum(d['trade_amount'] for d in trade_details.values())
print(f'\nTotal trade value: ${total_trade:,.2f}')

if not args.write:
    print('\nDRY RUN - no changes made. Use --write to record trade payments.')
    cur.close()
    conn.close()
    exit(0)

# Create backup
print('\nCreating backup...')
from table_protection import create_backup_before_delete
reserve_list = ','.join(repr(r) for r in charters)
backup_name = create_backup_before_delete(cur, 'charters', 
                                          condition=f"reserve_number IN ({reserve_list})")
print(f'✓ Backup: {backup_name}')

# Insert trade payments
print('\nCreating trade payments...')
for reserve, details in trade_details.items():
    # Insert payment record
    cur.execute("""
        INSERT INTO payments (
            reserve_number, 
            amount, 
            payment_date, 
            payment_method,
            notes,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        RETURNING payment_id
    """, (
        reserve,
        details['trade_amount'],
        details['charter_date'],
        'trade_of_services',
        'TRADE FOR SERVICES - Fibrenew rent exchange. Charters 017822/017823 provided in lieu of Fibrenew rent owed. Customer purchased alcohol at company discount. Total trade value: $6,050.75',
    ))
    payment_id = cur.fetchone()[0]
    
    print(f'  {reserve}: Created payment_id={payment_id} for ${details["trade_amount"]}')
    
    # Update charter
    new_paid = details['current_paid'] + details['trade_amount']
    new_balance = Decimal('0.00')
    
    cur.execute("""
        UPDATE charters
        SET paid_amount = %s,
            balance = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE reserve_number = %s
    """, (new_paid, new_balance, reserve))
    
    print(f'    Updated charter: paid_amount=${new_paid}, balance=${new_balance}')

conn.commit()
print(f'\n✓ Recorded ${total_trade:,.2f} in trade payments')
print('✓ Both charters balanced to $0.00')

# Verify
print('\n' + '='*100)
print('VERIFICATION')
print('='*100)
for reserve in charters:
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    c = cur.fetchone()
    print(f'{reserve}: total_due=${c[1]}, paid=${c[2]}, balance=${c[3]}')

cur.close()
conn.close()
print('\nDone.')
