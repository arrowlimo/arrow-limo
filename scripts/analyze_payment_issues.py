import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REMOVED***')
pg_cur = pg_conn.cursor()

print('=== OVERPAYMENT & ORPHAN ANALYSIS ===\n')

# 1. Top orphan reserves (most overpayment)
print('1️⃣ Top orphan reserves by payment amount:\n')
pg_cur.execute('''
    SELECT 
        p.reserve_number,
        COUNT(*) as payment_count,
        COALESCE(SUM(p.amount), 0) as total_paid,
        EXISTS(SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number) as has_charter
    FROM payments p
    WHERE NOT EXISTS (SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number)
    GROUP BY p.reserve_number
    ORDER BY SUM(p.amount) DESC
    LIMIT 15
''')

orphan_total = 0
for reserve, count, amount, has_charter in pg_cur.fetchall():
    reserve = reserve or 'NULL'
    amount = amount or 0
    print(f'  {str(reserve):10} | Payments: {count:3} | Amount: ${amount:>12,.2f}')
    orphan_total += amount

print(f'\nTotal orphan payments: ${orphan_total:,.2f}')

# 2. Duplicate payments (same reserve, same amount, same date)
print('\n2️⃣ Potential duplicate payments:\n')
pg_cur.execute('''
    SELECT 
        reserve_number,
        amount,
        payment_date,
        COUNT(*) as cnt
    FROM payments
    WHERE amount > 0
    GROUP BY reserve_number, amount, payment_date
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    LIMIT 10
''')

dup_count = 0
for reserve, amount, date, cnt in pg_cur.fetchall():
    print(f'  {reserve} | ${amount:>10,.2f} | {date} | Duplicates: {cnt}')
    dup_count += (cnt - 1)

print(f'\nTotal duplicate payment records found: {dup_count}')

# 3. Charters with overpayment (paid > charged)
print('\n3️⃣ Charters with overpayment (paid > charged):\n')
pg_cur.execute('''
    SELECT 
        c.reserve_number,
        c.total_amount_due as charges,
        COALESCE(SUM(p.amount), 0) as paid,
        COALESCE(SUM(p.amount), 0) - c.total_amount_due as overpayment
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number AND p.amount > 0
    WHERE c.total_amount_due > 0
    GROUP BY c.reserve_number, c.total_amount_due
    HAVING COALESCE(SUM(p.amount), 0) > c.total_amount_due
    ORDER BY ABS(COALESCE(SUM(p.amount), 0) - c.total_amount_due) DESC
    LIMIT 15
''')

over_total = 0
for reserve, charges, paid, over in pg_cur.fetchall():
    print(f'  {reserve} | Charges: ${charges:>10,.2f} | Paid: ${paid:>10,.2f} | Over: ${over:>10,.2f}')
    over_total += over

print(f'\nTotal overpayment on charters: ${over_total:,.2f}')

pg_cur.close()
pg_conn.close()
