import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

print('2012 Payroll by Month (excluding ADJ):')
print('Month  Entries    Gross Pay')
print('-' * 35)

cur.execute("""
    SELECT month, COUNT(*), SUM(gross_pay)
    FROM driver_payroll
    WHERE year = 2012 AND driver_id != 'ADJ'
    GROUP BY month
    ORDER BY month
""")

monthly_totals = []
for row in cur.fetchall():
    month, count, gross = row
    monthly_totals.append((month, count, gross))
    print(f'{month:>5}  {count:>7}  ${gross:>12,.2f}')

cur.execute("""
    SELECT SUM(gross_pay)
    FROM driver_payroll
    WHERE year = 2012 AND driver_id != 'ADJ'
""")

total = cur.fetchone()[0]
print('-' * 35)
print(f'Total: {sum(m[1] for m in monthly_totals):>7}  ${total:>12,.2f}')

print(f'\nTarget (from paystubs): ${116859.97:>12,.2f}')
gap = 116859.97 - float(total)
print(f'Gap:                    ${gap:>12,.2f}')

# Check for months with particularly low totals
print('\nMonths with gross pay < $5,000:')
for month, count, gross in monthly_totals:
    if gross < 5000:
        print(f'  Month {month}: ${gross:,.2f} ({count} entries)')

cur.close()
conn.close()
