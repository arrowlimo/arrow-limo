import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Check 2012 totals excluding ADJ
cur.execute("""
    SELECT COUNT(*), SUM(gross_pay), SUM(cpp), SUM(ei), SUM(tax)
    FROM driver_payroll
    WHERE year = 2012 AND driver_id != 'ADJ'
""")

r = cur.fetchone()
print(f'2012 Payroll (excluding ADJ entry):')
print(f'  Entries: {r[0]}')
print(f'  Gross: ${r[1]:.2f}')
print(f'  CPP: ${r[2]:.2f}')
print(f'  EI: ${r[3]:.2f}')
print(f'  Tax: ${r[4]:.2f}')

from decimal import Decimal

target_gross = Decimal('116859.97')
target_cpp = Decimal('1844.73')
target_ei = Decimal('1326.62')
target_tax = Decimal('1226.81')

print(f'\nTarget (from December 2012 paystub YTD):')
print(f'  Gross: ${target_gross:.2f}')
print(f'  CPP: ${target_cpp:.2f}')
print(f'  EI: ${target_ei:.2f}')
print(f'  Tax: ${target_tax:.2f}')

print(f'\nDiscrepancy:')
print(f'  Gross: ${r[1] - target_gross:.2f} ({"OVER" if r[1] > target_gross else "UNDER"})')
print(f'  CPP: ${r[2] - target_cpp:.2f} ({"OVER" if r[2] > target_cpp else "UNDER"})')
print(f'  EI: ${r[3] - target_ei:.2f} ({"OVER" if r[3] > target_ei else "UNDER"})')
print(f'  Tax: ${r[4] - target_tax:.2f} ({"OVER" if r[4] > target_tax else "UNDER"})')

cur.close()
conn.close()
