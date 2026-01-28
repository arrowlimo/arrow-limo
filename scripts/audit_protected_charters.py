#!/usr/bin/env python3
"""
Audit protected charters (Closed/closed_paid_verified/closed status).
These were likely checked by error in the legacy system.
Goal: Ensure they're properly matched for payments, balanced, and closed correctly.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

print("=" * 100)
print("PROTECTED CHARTER AUDIT (Closed/closed_paid_verified/closed status)")
print("=" * 100)

# 1. Summary of protected charters
print("\n1. PROTECTED CHARTERS SUMMARY:")
cur.execute("""
SELECT 
    c.status,
    COUNT(*) as count,
    SUM(COALESCE(cc.amount, 0)) as total_charges,
    SUM(COALESCE(p.amount, 0)) as total_payments,
    COUNT(CASE WHEN p.reserve_number IS NULL THEN 1 END) as unpaid_count
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.status IN ('Closed', 'closed_paid_verified', 'closed')
GROUP BY c.status
ORDER BY count DESC
""")
rows = cur.fetchall()
for status, count, charges, payments, unpaid in rows:
    paid = count - unpaid
    print(f"\n   {status}:")
    print(f"      Total charters: {count}")
    print(f"      With payments: {paid}")
    print(f"      Without payments (unpaid): {unpaid}")
    print(f"      Total charges: ${charges:,.2f}")
    print(f"      Total payments: ${payments:,.2f}")

# 2. Unpaid protected charters (need attention)
print("\n2. PROTECTED CHARTERS WITH UNPAID BALANCES:")
cur.execute("""
SELECT 
    c.reserve_number,
    c.charter_date,
    c.status,
    COALESCE(SUM(cc.amount), 0) as charges,
    COALESCE(SUM(p.amount), 0) as payments,
    COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(p.amount), 0) as balance_owing,
    COALESCE(c.notes, 'no notes') as notes
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.status IN ('Closed', 'closed_paid_verified', 'closed')
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.status, c.notes
HAVING COALESCE(SUM(cc.amount), 0) > 0
ORDER BY c.charter_date DESC
""")
rows = cur.fetchall()
print(f"\nTotal with unpaid balances: {len(rows)}")
if rows:
    for res, date, status, charges, payments, balance, notes in rows[:30]:
        notes_short = notes[:40] if notes else ""
        print(f"   {res:6} {date} {status:20} CHG:${charges:8,.2f} PAY:${payments:8,.2f} BAL:${balance:8,.2f} {notes_short}")
    if len(rows) > 30:
        print(f"   ... and {len(rows) - 30} more")

# 3. By amount owed (what needs fixing)
print("\n3. UNPAID BALANCES BY CATEGORY:")
cur.execute("""
WITH balance_data AS (
    SELECT 
        c.charter_id,
        COALESCE(SUM(cc.amount), 0) - COALESCE(SUM(p.amount), 0) as balance_owing
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.status IN ('Closed', 'closed_paid_verified', 'closed')
    GROUP BY c.charter_id
    HAVING COALESCE(SUM(cc.amount), 0) > 0
)
SELECT 
    COUNT(*) as count,
    ROUND(AVG(balance_owing), 2) as avg_balance,
    ROUND(SUM(balance_owing), 2) as total_balance,
    ROUND(MIN(balance_owing), 2) as min_balance,
    ROUND(MAX(balance_owing), 2) as max_balance,
    CASE 
        WHEN balance_owing < -500 THEN 'OVERPAID $500+'
        WHEN balance_owing < 0 THEN 'OVERPAID (minor)'
        WHEN balance_owing = 0.01 THEN 'Penny rounding'
        WHEN balance_owing < 1 THEN 'Under $1'
        WHEN balance_owing < 50 THEN '$1-$50'
        WHEN balance_owing < 500 THEN '$50-$500'
        ELSE '$500+'
    END as category
FROM balance_data
GROUP BY category
ORDER BY COUNT(*) DESC
""")
rows = cur.fetchall()
for count, avg_bal, total_bal, min_bal, max_bal, category in rows:
    print(f"\n   {category}:")
    print(f"      Charters: {count}")
    print(f"      Total: ${total_bal:,.2f}")
    print(f"      Average: ${avg_bal:,.2f}")
    print(f"      Range: ${min_bal:,.2f} to ${max_bal:,.2f}")

# 4. Charters with charges but NO payments at all
print("\n4. PROTECTED CHARTERS WITH CHARGES BUT ZERO PAYMENTS:")
cur.execute("""
SELECT 
    c.reserve_number,
    c.charter_date,
    c.status,
    SUM(cc.amount) as total_charges,
    COUNT(*) as charge_count
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.status IN ('Closed', 'closed_paid_verified', 'closed')
  AND cc.amount IS NOT NULL AND cc.amount > 0
  AND p.reserve_number IS NULL
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.status
ORDER BY total_charges DESC
LIMIT 20
""")
rows = cur.fetchall()
print(f"\nCount: {len(rows)}")
for res, date, status, charges, charge_count in rows:
    print(f"   {res:6} {date} {status:20} Charges: ${charges:8,.2f} ({charge_count} items)")

# 5. Status breakdown (which should be cancelled vs kept)
print("\n5. RECOMMENDATIONS:")
print("""
   PENNY ROUNDING ($0.01):
      → Write off as rounding error (DELETE charge OR reduce to $0.00)
      
   UNDER $1 (excluding $0.01):
      → Either match missing payment OR write off
      
   $1-$50:
      → Search for missing payments (check banking, Square, cash)
      → If genuine unpaid: cancel charter + delete charges
      
   $50-$500:
      → High priority: match to payments or investigate
      → May indicate sync errors from legacy system
      
   $500+:
      → Very high priority: verify with original records
      → May be legitimate write-offs documented in notes
""")

print("\n" + "=" * 100)
cur.close()
conn.close()
