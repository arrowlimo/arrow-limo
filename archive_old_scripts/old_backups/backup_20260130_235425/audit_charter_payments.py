import psycopg2

pg_conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
pg_cur = pg_conn.cursor()

print('=== CHARTER-PAYMENT VERIFICATION AUDIT ===\n')

# 1. Check total charges vs payments
print('1️⃣ Total charges vs total payments:\n')
pg_cur.execute('SELECT COALESCE(SUM(total_amount_due), 0) FROM charters WHERE total_amount_due IS NOT NULL')
total_charges = pg_cur.fetchone()[0]
print(f'   Total charges (charters): ${total_charges:,.2f}')

pg_cur.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE amount > 0')
total_payments = pg_cur.fetchone()[0]
print(f'   Total payments: ${total_payments:,.2f}')
print(f'   Outstanding (should be close): ${total_charges - total_payments:,.2f}')

# 2. Charters with payments
print('\n2️⃣ Payment coverage:\n')
pg_cur.execute('''
    SELECT COUNT(*) as total_charters,
           COUNT(DISTINCT c.reserve_number) FILTER (WHERE p.amount > 0) as charters_with_payments
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number AND p.amount > 0
''')
total_c, with_payments = pg_cur.fetchone()
print(f'   Total charters: {total_c}')
print(f'   Charters with payments: {with_payments}')
print(f'   Coverage: {100*with_payments/total_c:.1f}%')

# 3. Orphan payments (no matching charter)
print('\n3️⃣ Orphan payments (no charter):\n')
pg_cur.execute('''
    SELECT COUNT(*) FROM payments p
    WHERE NOT EXISTS (
        SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
    )
''')
orphan_count = pg_cur.fetchone()[0]
print(f'   Orphan payments: {orphan_count}')

if orphan_count > 0:
    pg_cur.execute('''
        SELECT p.reserve_number, p.amount, p.payment_date
        FROM payments p
        WHERE NOT EXISTS (
            SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
        )
        LIMIT 5
    ''')
    for row in pg_cur.fetchall():
        print(f'     {row[0]} | ${row[1]:,.2f} | {row[2]}')

# 4. Sample balance verification
print('\n4️⃣ Balance verification samples:\n')
pg_cur.execute('''
    SELECT 
        c.reserve_number,
        c.total_amount_due,
        COALESCE(SUM(p.amount), 0) as total_paid,
        c.total_amount_due - COALESCE(SUM(p.amount), 0) as balance_outstanding
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number AND p.amount > 0
    WHERE c.total_amount_due > 0
    GROUP BY c.reserve_number, c.total_amount_due
    ORDER BY RANDOM()
    LIMIT 10
''')

mismatches = 0
for reserve, charges, paid, balance in pg_cur.fetchall():
    status = '✅' if balance >= 0 else '❌'
    print(f'{status} {reserve} | Charges: ${charges:>10,.2f} | Paid: ${paid:>10,.2f} | Balance: ${balance:>10,.2f}')
    if balance < 0:
        mismatches += 1

if mismatches > 0:
    print(f'\n⚠️ Found {mismatches} negative balances in sample!')

# 5. Count charters with outstanding balance
print('\n5️⃣ Outstanding balance distribution:\n')
pg_cur.execute('''
    SELECT 
        CASE 
            WHEN total_amount_due IS NULL THEN 'No charges'
            WHEN total_amount_due = 0 THEN 'Zero charges'
            ELSE 'Has charges'
        END as charge_status,
        COUNT(*) as cnt
    FROM charters
    GROUP BY charge_status
    ORDER BY cnt DESC
''')

for status, cnt in pg_cur.fetchall():
    print(f'   {status}: {cnt}')

pg_cur.close()
pg_conn.close()
