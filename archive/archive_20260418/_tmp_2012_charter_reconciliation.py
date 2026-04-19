#!/usr/bin/env python3
"""
Create detailed 2012 charter payment reconciliation.
Shows each charter with amount owed vs. payments received.
"""

import psycopg2
from decimal import Decimal

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

# Get all 2012 charters with their payments
query = """
SELECT 
    c.charter_id,
    c.reserve_number,
    c.charter_date,
    COALESCE(c.grand_total, c.total_amount_due, 0) as amount_owed,
    COALESCE(SUM(cp.amount), 0) as total_paid,
    COALESCE(SUM(cp.amount), 0) - COALESCE(c.grand_total, c.total_amount_due, 0) as balance
FROM charters c
LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.grand_total, c.total_amount_due
ORDER BY c.charter_date, c.charter_id;
"""

cur.execute(query)
rows = cur.fetchall()

print(f"\n{'Charter':<10} {'Reserve':<12} {'Date':<12} {'Amount Owed':<14} {'Paid':<14} {'Balance':<14} {'Status':<10}")
print("=" * 96)

total_owed = Decimal('0')
total_paid = Decimal('0')
fully_paid = 0
partial = 0
unpaid = 0

for charter_id, reserve, charter_date, owed, paid, balance in rows:
    owed = Decimal(str(owed)) if owed else Decimal('0')
    paid = Decimal(str(paid)) if paid else Decimal('0')
    balance = Decimal(str(balance)) if balance else Decimal('0')
    
    total_owed += owed
    total_paid += paid
    
    # Determine status
    if balance == 0 or abs(balance) < Decimal('0.01'):  # Essentially zero (within $0.01)
        status = 'PAID'
        fully_paid += 1
    elif balance > 0:
        status = 'OVERPAID'
        fully_paid += 1
    elif paid == 0:
        status = 'UNPAID'
        unpaid += 1
    else:
        status = 'PARTIAL'
        partial += 1
    
    print(f"{charter_id:<10} {reserve:<12} {str(charter_date):<12} ${owed:>11,.2f} ${paid:>11,.2f} ${balance:>11,.2f} {status:<10}")

print("=" * 96)
print(f"{'TOTAL':<10} {'':<12} {'':<12} ${total_owed:>11,.2f} ${total_paid:>11,.2f} ${(total_paid - total_owed):>11,.2f}")

print(f"\n=== RECONCILIATION SUMMARY ===")
print(f"Total charters: {len(rows)}")
print(f"Fully paid (including overpaid): {fully_paid}")
print(f"Partially paid: {partial}")
print(f"Unpaid: {unpaid}")
print(f"\nTotal amount owed: ${total_owed:,.2f}")
print(f"Total payments received: ${total_paid:,.2f}")
print(f"Net variance: ${(total_paid - total_owed):,.2f}")

# Check for any significant variances
print(f"\n=== VARIANCES > $1.00 ===")
variance_query = """
SELECT 
    c.charter_id,
    c.reserve_number,
    c.charter_date,
    COALESCE(c.grand_total, c.total_amount_due, 0) as amount_owed,
    COALESCE(SUM(cp.amount), 0) as total_paid,
    COALESCE(SUM(cp.amount), 0) - COALESCE(c.grand_total, c.total_amount_due, 0) as variance
FROM charters c
LEFT JOIN charter_payments cp ON cp.charter_id = c.reserve_number
WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.grand_total, c.total_amount_due
HAVING ABS(COALESCE(SUM(cp.amount), 0) - COALESCE(c.grand_total, c.total_amount_due, 0)) > 1.00
ORDER BY ABS(COALESCE(SUM(cp.amount), 0) - COALESCE(c.grand_total, c.total_amount_due, 0)) DESC;
"""

cur.execute(variance_query)
variances = cur.fetchall()
if variances:
    print(f"{'Charter':<10} {'Reserve':<12} {'Date':<12} {'Amount Owed':<14} {'Paid':<14} {'Variance':<14}")
    for charter_id, reserve, charter_date, owed, paid, variance in variances:
        print(f"{charter_id:<10} {reserve:<12} {str(charter_date):<12} ${float(owed):>11,.2f} ${float(paid):>11,.2f} ${float(variance):>11,.2f}")
    print(f"Found {len(variances)} charters with variance > $1.00")
else:
    print("No significant variances found - all charters reconcile within $1.00")

cur.close()
conn.close()
