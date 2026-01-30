import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST','localhost'),
    dbname=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

reserves = ['014380','014411','015911','016213','016284','016530',
            '016922','017101','017860','018424','019238']

print('Charter Status Summary (from calendar import):')
print('='*90)
print(f'{"Reserve":8} | {"Cancelled":9} | {"Total":10} | {"Paid":10} | {"Balance":10} | {"Credits":15}')
print('-'*90)

validated = []
needs_review = []

for res in reserves:
    cur.execute("""
        SELECT cancelled, total_amount_due, paid_amount, balance 
        FROM charters WHERE reserve_number=%s
    """, (res,))
    c = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(credit_amount), 0) 
        FROM charter_credit_ledger 
        WHERE source_reserve_number=%s
    """, (res,))
    cr = cur.fetchone()
    
    if c:
        canc = 'Yes' if c[0] else 'No'
        total = c[1] if c[1] is not None else 0
        paid = c[2] if c[2] is not None else 0
        balance = c[3] if c[3] is not None else 0
        credit_count = cr[0]
        credit_sum = cr[1]
        
        credit_str = f"{credit_count}x${credit_sum}" if credit_count > 0 else "None"
        
        print(f'{res:8} | {canc:9} | ${total:9.2f} | ${paid:9.2f} | ${balance:9.2f} | {credit_str:15}')
        
        # Validation logic
        if res == '019238':
            # Should be cancelled, no credits (payment was moved)
            if c[0] and credit_count == 0:
                validated.append(res)
            else:
                needs_review.append((res, 'Should be cancelled with no credits (payment moved to 018885)'))
        elif abs(balance) < 0.01:
            validated.append(res)
        else:
            needs_review.append((res, f'Balance ${balance:.2f} not zero'))
    else:
        print(f'{res:8} | NOT FOUND')
        needs_review.append((res, 'Charter not found'))

print('='*90)
print(f'\nValidated: {len(validated)}/{len(reserves)}')
print(f'Needs Review: {len(needs_review)}/{len(reserves)}')

if needs_review:
    print('\nCharters needing review:')
    for res, reason in needs_review:
        print(f'  {res}: {reason}')

cur.close()
conn.close()
