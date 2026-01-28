#!/usr/bin/env python3
"""
Verify the protected charter findings with detailed sample inspection.
Check for: double-counting, schema issues, data anomalies.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("VERIFICATION: Protected Charter Overpayment Claims")
print("=" * 100)

# 1. Pick a few specific "overpaid" charters and show complete breakdown
print("\n1. SAMPLE OVERPAID CHARTERS - COMPLETE BREAKDOWN:")
cur.execute("""
SELECT c.charter_id, c.reserve_number, c.charter_date, c.status
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.status = 'Closed'
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.status
HAVING COALESCE(SUM(cc.amount), 0) > 0
  AND COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(p.amount), 0) < -500
ORDER BY COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(p.amount), 0) ASC
LIMIT 5
""")
overpaid_samples = cur.fetchall()

for charter_id, reserve, date, status in overpaid_samples:
    print(f"\n   {reserve} (Charter ID: {charter_id}, Date: {date}, Status: {status}):")
    
    # Get charges
    cur.execute("""
    SELECT SUM(amount), COUNT(*) as count
    FROM charter_charges
    WHERE charter_id = %s
    """, (charter_id,))
    charge_sum, charge_count = cur.fetchone()
    print(f"      CHARGES: ${charge_sum or 0:,.2f} ({charge_count} records)")
    
    # Get payments - show EACH payment
    cur.execute("""
    SELECT payment_id, payment_date, amount, payment_method, notes
    FROM payments
    WHERE reserve_number = %s
    ORDER BY payment_date
    """, (reserve,))
    payments = cur.fetchall()
    pay_total = sum(p[2] for p in payments)
    print(f"      PAYMENTS: ${pay_total:,.2f} ({len(payments)} records)")
    for pid, pdate, amt, method, pnotes in payments[:5]:
        print(f"         {pdate} {method:15} ${amt:8,.2f}  (ID: {pid})")
    if len(payments) > 5:
        print(f"         ... and {len(payments)-5} more")
    
    print(f"      BALANCE: ${(charge_sum or 0) - pay_total:,.2f}")

# 2. DUPLICATE PAYMENT CHECK
print("\n\n2. DUPLICATE PAYMENT CHECK (same reserve, date, amount):")
cur.execute("""
SELECT 
    reserve_number,
    payment_date,
    amount,
    COUNT(*) as count,
    MIN(payment_id) as first_id,
    MAX(payment_id) as last_id
FROM payments
WHERE payment_date >= '2024-01-01'
GROUP BY reserve_number, payment_date, amount
HAVING COUNT(*) > 1
LIMIT 10
""")

# 3. Total payments vs total charges (Closed status)
print("\n\n3. TOTAL COMPARISON (Closed status only):")
cur.execute("""
SELECT 
    COUNT(DISTINCT c.charter_id) as charter_count,
    ROUND(SUM(COALESCE(cc.amount, 0))::numeric, 2) as total_charges,
    ROUND(SUM(COALESCE(p.amount, 0))::numeric, 2) as total_payments,
    ROUND(SUM(COALESCE(cc.amount, 0)) - SUM(COALESCE(p.amount, 0))::numeric, 2) as net_balance
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.status = 'Closed'
  AND COALESCE(cc.amount, 0) > 0
""")
result = cur.fetchone()
print(f"   Closed charters with charges: {result[0]:,}")
print(f"   Total charges: ${result[1]:,.2f}")
print(f"   Total payments matched: ${result[2]:,.2f}")
print(f"   Net (Charges - Payments): ${result[3]:,.2f}")

# 4. Check charter_charges for oddities
print("\n\n4. CHARTER_CHARGES TABLE SCHEMA CHECK:")
cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'charter_charges'
ORDER BY ordinal_position
""")
cols = cur.fetchall()
for col_name, col_type in cols:
    print(f"   {col_name:25} {col_type}")

# 5. Check if payments are linked correctly
print("\n\n5. PAYMENT LINKING VERIFICATION:")
cur.execute("""
SELECT 
    COUNT(*) as total_payments,
    COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as with_reserve,
    COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as null_reserve,
    COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as with_charter_id,
    COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as null_charter_id
FROM payments
""")
result = cur.fetchone()
print(f"   Total payments: {result[0]:,}")
print(f"   With reserve_number: {result[1]:,}")
print(f"   NULL reserve_number: {result[2]:,}")
print(f"   With charter_id: {result[3]:,}")
print(f"   NULL charter_id: {result[4]:,}")

# 6. Verify aggregation isn't causing double-counting via LEFT JOIN
print("\n\n6. DOUBLE-COUNTING CHECK (LEFT JOIN issue):")
cur.execute("""
SELECT c.charter_id, c.reserve_number,
       COALESCE(SUM(cc.amount), 0) as charges_sum,
       COALESCE(SUM(p.amount), 0) as payments_sum
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.reserve_number IN ('019640', '019649', '019646')
GROUP BY c.charter_id, c.reserve_number
""")
rows = cur.fetchall()
print("   Checking specific reserves from overpaid list:")
for cid, res, chg, pay in rows:
    print(f"      {res}: Charges={chg:,.2f}, Payments={pay:,.2f}, Balance={chg-pay:,.2f}")

print("\n" + "=" * 100)
cur.close()
conn.close()
