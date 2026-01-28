#!/usr/bin/env python3
"""Recategorize E-transfers with proper employee identification."""
import psycopg2
import os
import re

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Find all unmatched E-transfers
query = '''
SELECT 
    bt.transaction_id,
    bt.transaction_date,
    bt.credit_amount,
    bt.description
FROM banking_transactions bt
WHERE bt.credit_amount > 0
  AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND p.payment_date::date >= bt.transaction_date::date - INTERVAL '7 days'
      AND p.payment_date::date <= bt.transaction_date::date + INTERVAL '7 days'
  )
ORDER BY bt.transaction_date DESC, bt.credit_amount DESC;
'''

cur.execute(query)
results = cur.fetchall()
cur.close()
conn.close()

# Known employees/drivers
employee_keywords = [
    'BARB PEACOCK',
    'DAVID WILLIAM RICHARD',
    'DAVIDRICHARD',
    'DAVID RICHARD',
    'MATTHEW RICHARD',
    'PAUL RICHARD',
    'MICHAEL',
    'JERRY',
    'JEANNIE SHILLINGTON',
    'SCHANDRIP',
]

# Known vendors (exclude from employee)
vendor_keywords = [
    'AARON MACHINE',
    'HEFFNER AUTO',
    'COMBINED INS',
    'MCDONALD',
    'SQUARE',
]

# Categorize
employee_etransfers = []
customer_etransfers = []
vendor_etransfers = []

for row in results:
    tid, date, amount, desc = row
    
    is_employee = False
    is_vendor = False
    
    # Check vendor first (exclude from employee)
    for vendor_keyword in vendor_keywords:
        if vendor_keyword in desc.upper():
            vendor_etransfers.append((tid, date, amount, desc))
            is_vendor = True
            break
    
    if is_vendor:
        continue
    
    # Check employee
    for emp_keyword in employee_keywords:
        if emp_keyword in desc.upper():
            employee_etransfers.append((tid, date, amount, desc))
            is_employee = True
            break
    
    if not is_employee:
        customer_etransfers.append((tid, date, amount, desc))

# Display
print("\n" + "=" * 150)
print("UNMATCHED E-TRANSFERS - RECATEGORIZED".center(150))
print("=" * 150)

print(f"\n🔴 EMPLOYEE/DRIVER PAYMENTS: {len(employee_etransfers)} transfers | ${sum(x[2] for x in employee_etransfers):,.2f}")
print("-" * 150)
for tid, date, amount, desc in employee_etransfers[:30]:
    print(f"[{str(date)[:10]}] ${amount:>10.2f}  {desc}")
if len(employee_etransfers) > 30:
    print(f"... and {len(employee_etransfers) - 30} more")

print(f"\n👥 CUSTOMER E-TRANSFERS: {len(customer_etransfers)} transfers | ${sum(x[2] for x in customer_etransfers):,.2f}")
print("-" * 150)
for tid, date, amount, desc in customer_etransfers[:30]:
    print(f"[{str(date)[:10]}] ${amount:>10.2f}  {desc}")
if len(customer_etransfers) > 30:
    print(f"... and {len(customer_etransfers) - 30} more")

print(f"\n🏢 VENDOR/CONTRACTOR E-TRANSFERS: {len(vendor_etransfers)} transfers | ${sum(x[2] for x in vendor_etransfers):,.2f}")
print("-" * 150)
for tid, date, amount, desc in vendor_etransfers[:30]:
    print(f"[{str(date)[:10]}] ${amount:>10.2f}  {desc}")
if len(vendor_etransfers) > 30:
    print(f"... and {len(vendor_etransfers) - 30} more")

print("\n" + "=" * 150)
emp_total = sum(x[2] for x in employee_etransfers)
cust_total = sum(x[2] for x in customer_etransfers)
vend_total = sum(x[2] for x in vendor_etransfers)
print(f"EMPLOYEE PAYMENTS:      {len(employee_etransfers):>6} | ${emp_total:>12,.2f}")
print(f"CUSTOMER PAYMENTS:      {len(customer_etransfers):>6} | ${cust_total:>12,.2f}")
print(f"VENDOR PAYMENTS:        {len(vendor_etransfers):>6} | ${vend_total:>12,.2f}")
print(f"TOTAL E-TRANSFERS:      {len(results):>6} | ${emp_total + cust_total + vend_total:>12,.2f}")
print("=" * 150 + "\n")
