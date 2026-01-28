#!/usr/bin/env python3
"""
Find orphaned payments: 2025+ payments matched to old charters.
Since reserve_number is a PRIMARY KEY in LMS, it can only be reused if 
a charter was cancelled and reopened. This should be extremely rare.

Likely cause: Import error that matched payments to wrong reserve_number.
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
print("ORPHANED PAYMENTS AUDIT: Recent payments (2025+) on ancient charters (pre-2020)")
print("=" * 100)

# 1. Find payments 2025+ attached to charters pre-2020
print("\n1. RECENT PAYMENTS (2025+) ON ANCIENT CHARTERS (pre-2020):")
cur.execute("""
SELECT 
    p.payment_id,
    p.reserve_number,
    p.payment_date,
    p.amount,
    c.charter_id,
    c.charter_date,
    c.status,
    EXTRACT(YEAR FROM p.payment_date) - EXTRACT(YEAR FROM c.charter_date) as year_gap
FROM payments p
JOIN charters c ON c.reserve_number = p.reserve_number
WHERE p.payment_date >= '2025-01-01'
  AND c.charter_date < '2020-01-01'
ORDER BY c.charter_date ASC, p.payment_date DESC
LIMIT 50
""")
rows = cur.fetchall()
print(f"\nFound {len(rows)} recent payments on ancient charters:")
for pid, res, pdate, amt, cid, cdate, status, gap in rows:
    print(f"   {res} | Charter: {cdate} | Payment: {pdate} ({gap} year gap!) | ${amt:8,.2f} | {status}")

# 2. Summary by year gap
print("\n\n2. RECENT PAYMENTS BY YEAR GAP (payment year - charter year):")
cur.execute("""
WITH gap_data AS (
    SELECT 
        EXTRACT(YEAR FROM p.payment_date) - EXTRACT(YEAR FROM c.charter_date) as year_gap,
        COUNT(*) as count,
        SUM(p.amount) as total
    FROM payments p
    JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.payment_date >= '2025-01-01'
      AND c.charter_date < '2020-01-01'
    GROUP BY year_gap
)
SELECT year_gap, count, ROUND(total::numeric, 2) as total
FROM gap_data
ORDER BY year_gap DESC
""")
rows = cur.fetchall()
for gap, count, total in rows:
    print(f"   {gap:3.0f} years: {count:4} payments, ${total:12,.2f}")

# 3. Check if these charters were ACTUALLY cancelled and reopened
print("\n\n3. WERE THESE ANCIENT CHARTERS CANCELLED AND REOPENED?")
cur.execute("""
SELECT 
    c.reserve_number,
    c.charter_date,
    c.status,
    COUNT(DISTINCT p.payment_id) as payment_count,
    MIN(p.payment_date) as first_payment,
    MAX(p.payment_date) as last_payment,
    COALESCE(c.notes, 'no notes') as notes
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.charter_date < '2020-01-01'
  AND EXISTS (
    SELECT 1 FROM payments p2
    WHERE p2.reserve_number = c.reserve_number
      AND p2.payment_date >= '2025-01-01'
  )
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.status, c.notes
ORDER BY c.charter_date DESC
LIMIT 20
""")
rows = cur.fetchall()
print(f"\nAncient charters with 2025+ payments:")
for res, cdate, status, pay_count, first_pay, last_pay, notes in rows:
    notes_short = notes[:50] if notes else ""
    print(f"   {res:6} ({cdate}) Status: {status:15} Pay range: {first_pay} to {last_pay}")
    print(f"           Notes: {notes_short}")

# 4. Calculate impact of removing these orphaned payments
print("\n\n4. IMPACT OF REMOVING 2025+ PAYMENTS FROM PRE-2020 CHARTERS:")
cur.execute("""
SELECT 
    COUNT(DISTINCT p.payment_id) as orphaned_payment_count,
    SUM(p.amount) as orphaned_total,
    COUNT(DISTINCT c.charter_id) as affected_charter_count
FROM payments p
JOIN charters c ON c.reserve_number = p.reserve_number
WHERE p.payment_date >= '2025-01-01'
  AND c.charter_date < '2020-01-01'
""")
result = cur.fetchone()
print(f"   Orphaned payments: {result[0]:,}")
print(f"   Total amount: ${result[1]:,.2f}")
print(f"   Affected charters: {result[2]:,}")

# 5. What would balances look like WITHOUT these orphaned payments?
print("\n\n5. CHARTER BALANCES BEFORE/AFTER REMOVING ORPHANED PAYMENTS:")
cur.execute("""
WITH with_orphans AS (
    SELECT 
        COUNT(DISTINCT c.charter_id) as count,
        SUM(COALESCE(cc.amount, 0)) - SUM(COALESCE(p.amount, 0)) as net_balance
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    WHERE c.status = 'Closed' AND c.charter_date < '2020-01-01'
),
without_orphans AS (
    SELECT 
        COUNT(DISTINCT c.charter_id) as count,
        SUM(COALESCE(cc.amount, 0)) - SUM(COALESCE(p.amount, 0)) as net_balance
    FROM charters c
    LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number 
        AND NOT (p.payment_date >= '2025-01-01')
    WHERE c.status = 'Closed' AND c.charter_date < '2020-01-01'
)
SELECT 
    'WITH orphaned payments' as scenario,
    (SELECT count FROM with_orphans) as charter_count,
    ROUND((SELECT net_balance FROM with_orphans)::numeric, 2) as net_balance
UNION ALL
SELECT 
    'WITHOUT orphaned payments' as scenario,
    (SELECT count FROM without_orphans) as charter_count,
    ROUND((SELECT net_balance FROM without_orphans)::numeric, 2) as net_balance
""")
rows = cur.fetchall()
for scenario, count, balance in rows:
    print(f"   {scenario:30} {count:,} charters, Net balance: ${balance:,.2f}")

print("\n" + "=" * 100)
cur.close()
conn.close()
