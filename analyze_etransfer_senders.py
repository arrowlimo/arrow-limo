#!/usr/bin/env python3
"""Recategorize E-transfers: identify employee/driver payments vs customer payments."""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Find all unmatched E-transfers with names
query = '''
SELECT DISTINCT
    SUBSTRING(bt.description FROM 'E-TRANSFER.*?([A-Z][A-Za-z ]+)') as sender_name,
    COUNT(*) as count,
    SUM(bt.credit_amount) as total,
    ARRAY_AGG(DISTINCT bt.description ORDER BY bt.description) as samples
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '7 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '7 days'
  )
GROUP BY sender_name
ORDER BY total DESC;
'''

cur.execute(query)
results = cur.fetchall()
cur.close()
conn.close()

# Known employee/driver names
employees = {
    'MICHAEL': 'Employee/Driver',
    'RICHARD': 'Employee/Driver', 
    'JERRY': 'Employee/Driver',
    'SCHANDRIP': 'Employee/Driver',
    'JEANNIE': 'Employee/Driver',
    'SHILLINGTON': 'Employee/Driver',
    'AARON': 'Employee/Driver (Aaron Machine Shop)',
    'PAUL': 'Employee/Driver',
    'ASHLEY': 'Employee/Driver',
    'BARB': 'Employee/Driver',
    'KEVIN': 'Employee/Driver',
    'DAVID': 'Employee/Driver',
    'PAYTON': 'Employee/Driver',
    'EMILY': 'Customer or Employee?',
    'SHERRI': 'Customer or Employee?',
    'SUZANNE': 'Customer or Employee?',
    'JUSTIN': 'Customer or Employee?',
}

print("\n" + "=" * 140)
print("E-TRANSFER SENDERS - UNMATCHED DEPOSITS".center(140))
print("=" * 140)

employee_total = 0
customer_total = 0
unknown_total = 0

print("\n🔴 EMPLOYEES/DRIVERS (E-transfer payments):")
print("-" * 140)
print(f"{'Sender Name':<30} | {'Count':>6} | {'Total Amount':>14} | {'Status':<25} | {'Sample Description':<60}")
print("-" * 140)

for row in results:
    name, count, total, samples = row
    if not name:
        continue
    
    name_clean = name.strip() if name else 'UNKNOWN'
    
    # Categorize
    status = 'Customer'
    first_name = name_clean.split()[0].upper() if name_clean else ''
    
    for emp_key, emp_label in employees.items():
        if emp_key in name_clean.upper():
            status = emp_label
            break
    
    if 'Employee' in status or 'Driver' in status:
        employee_total += total
        print(f"{name_clean:<30} | {count:>6} | ${total:>12,.2f} | {status:<25} | {samples[0][:57] if samples else '':<60}")
    elif '?' in status:
        unknown_total += total
        print(f"{name_clean:<30} | {count:>6} | ${total:>12,.2f} | {status:<25} | {samples[0][:57] if samples else '':<60}")
    else:
        customer_total += total

print("\n\n👥 CUSTOMERS (E-transfer payments - likely charter deposits):")
print("-" * 140)
print(f"{'Sender Name':<30} | {'Count':>6} | {'Total Amount':>14} | {'Status':<25} | {'Sample Description':<60}")
print("-" * 140)

for row in results:
    name, count, total, samples = row
    if not name:
        continue
    
    name_clean = name.strip() if name else 'UNKNOWN'
    
    # Categorize
    status = 'Customer'
    first_name = name_clean.split()[0].upper() if name_clean else ''
    
    for emp_key, emp_label in employees.items():
        if emp_key in name_clean.upper():
            status = emp_label
            break
    
    if 'Employee' not in status and '?' not in status:
        print(f"{name_clean:<30} | {count:>6} | ${total:>12,.2f} | {status:<25} | {samples[0][:57] if samples else '':<60}")

print("\n❓ UNCLEAR (likely employees but need verification):")
print("-" * 140)
for row in results:
    name, count, total, samples = row
    if not name:
        continue
    
    name_clean = name.strip() if name else 'UNKNOWN'
    status = 'Customer'
    
    for emp_key, emp_label in employees.items():
        if emp_key in name_clean.upper():
            status = emp_label
            break
    
    if '?' in status:
        print(f"{name_clean:<30} | {count:>6} | ${total:>12,.2f} | {status:<25} | {samples[0][:57] if samples else '':<60}")

print("\n\n" + "=" * 140)
print("SUMMARY")
print("=" * 140)
print(f"Identified Employees/Drivers:  ${employee_total:>12,.2f}")
print(f"Likely Customers:              ${customer_total:>12,.2f}")
print(f"Unclear (need review):         ${unknown_total:>12,.2f}")
print(f"TOTAL E-TRANSFERS:             ${employee_total + customer_total + unknown_total:>12,.2f}")
print("=" * 140 + "\n")
