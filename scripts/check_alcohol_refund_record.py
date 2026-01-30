#!/usr/bin/env python
"""
Check if alcohol refund to Shaye Callin was recorded as a negative payment or adjustment.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('CHECK FOR ALCOHOL REFUND RECORD')
print('='*100)

# Check for negative payments or refunds for these charters
for reserve in ['017822', '017823']:
    print(f'\n{"="*100}')
    print(f'CHARTER {reserve}')
    print(f'{"="*100}')
    
    # Charter details
    cur.execute("""
        SELECT total_amount_due, paid_amount, balance, notes
        FROM charters WHERE reserve_number = %s
    """, (reserve,))
    c = cur.fetchone()
    print(f'\nCharter: total_due=${c[0]}, paid=${c[1]}, balance=${c[2]}')
    if c[3]:
        print(f'Notes: {c[3][:200]}...')
    
    # Charges
    cur.execute("""
        SELECT description, amount
        FROM charter_charges
        WHERE reserve_number = %s
        ORDER BY amount DESC
    """, (reserve,))
    charges = cur.fetchall()
    print(f'\nCharges ({len(charges)} total):')
    for ch in charges:
        print(f'  ${ch[1]:>10.2f} - {ch[0][:60]}')
    
    # All payments (including negative)
    cur.execute("""
        SELECT payment_id, amount, payment_date, payment_method, notes
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, amount
    """, (reserve,))
    payments = cur.fetchall()
    print(f'\nPayments ({len(payments)} total):')
    for p in payments:
        print(f'  ${p[1]:>10.2f} on {p[2]} via {p[3] or "N/A"} (id={p[0]})')
        if p[4]:
            print(f'    Notes: {p[4][:80]}')

# Check if there's a charter_charge with negative amount (refund)
cur.execute("""
    SELECT c.reserve_number, c.charter_date, cc.description, cc.amount
    FROM charter_charges cc
    INNER JOIN charters c ON c.reserve_number = cc.reserve_number
    WHERE c.charter_date >= '2023-07-01'
      AND c.charter_date <= '2023-08-31'
      AND cc.amount < 0
    ORDER BY cc.amount
""")
negative_charges = cur.fetchall()

print(f'\n{"="*100}')
print('NEGATIVE CHARGES (REFUNDS) IN JULY-AUGUST 2023')
print('='*100)
for nc in negative_charges:
    print(f'{nc[0]} ({nc[1]}): ${nc[3]:,.2f} - {nc[2][:60]}')

# Check if alcohol is mentioned in any charges for these charters
cur.execute("""
    SELECT description, amount
    FROM charter_charges
    WHERE reserve_number IN ('017822', '017823')
      AND (description ILIKE '%alcohol%' OR description ILIKE '%liquor%' OR description ILIKE '%beverage%')
""")
alcohol_charges = cur.fetchall()

print(f'\n{"="*100}')
print('ALCOHOL/LIQUOR CHARGES FOR 017822/017823')
print('='*100)
if alcohol_charges:
    for ac in alcohol_charges:
        print(f'  ${ac[1]:,.2f} - {ac[0]}')
else:
    print('  No alcohol/liquor charges found')

cur.close()
conn.close()
print('\nDone.')
