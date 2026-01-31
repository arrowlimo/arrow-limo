#!/usr/bin/env python
import psycopg2
from decimal import Decimal

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print('='*100)
print('Zero-charge charters analysis (total_amount_due IS NULL or = 0)')
print('='*100)

cur.execute("""
    SELECT 
      COUNT(*) FILTER (WHERE total_amount_due IS NULL) AS null_due,
      COUNT(*) FILTER (WHERE COALESCE(total_amount_due,0)=0) AS zero_due
    FROM charters
""")
null_due, zero_due = cur.fetchone()
print(f"Total with NULL due: {null_due:,}")
print(f"Total with 0.00 due (includes NULL treated as 0): {zero_due:,}")

# Breakdown by cancellation and status
cur.execute("""
    SELECT 
      COALESCE(CAST(cancelled AS TEXT),'NULL') AS cancelled,
      COALESCE(NULLIF(TRIM(status),''),'(empty)') AS status,
      COUNT(*) AS cnt,
      SUM(CASE WHEN COALESCE(paid_amount,0)>0 THEN 1 ELSE 0 END) AS with_payments
    FROM charters
    WHERE COALESCE(total_amount_due,0)=0
    GROUP BY 1,2
    ORDER BY 3 DESC
""")
rows = cur.fetchall()
print('\nBreakdown (cancelled, status):')
for cancelled, status, cnt, with_pay in rows[:50]:
    print(f"  cancelled={cancelled:<6} status={status:<12} count={cnt:>6} with_payments={with_pay:>6}")

# Are all zero-charge charters cancelled?
all_cancelled = all(r[0] in ('true','t','1','True','TRUE') for r in rows)
print('\nAll zero-charge charters cancelled? ', 'YES' if all_cancelled else 'NO')

# Show sample of zero-charge not cancelled
cur.execute("""
    SELECT reserve_number, charter_date, account_number, status, cancelled,
           COALESCE(paid_amount,0) AS paid, COALESCE(balance,0) AS balance
    FROM charters
    WHERE COALESCE(total_amount_due,0)=0
      AND NOT COALESCE(cancelled::boolean, false)
    ORDER BY COALESCE(paid_amount,0) DESC NULLS LAST
    LIMIT 25
""")
print('\nSample zero-charge charters NOT cancelled:')
for r in cur.fetchall():
    print('  ', r)

# Count zero-charge with positive payments (likely credits)
cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE COALESCE(total_amount_due,0)=0
      AND COALESCE(paid_amount,0) > 0
""")
print(f"\nZero-charge with payments > 0: {cur.fetchone()[0]:,}")

# Recent ones (2024+) summary
cur.execute("""
    SELECT date_part('year', charter_date)::int AS year, COUNT(*)
    FROM charters
    WHERE COALESCE(total_amount_due,0)=0
    GROUP BY 1
    ORDER BY 1 DESC
""")
print('\nBy year (zero-charge):')
for y,c in cur.fetchall():
    print(f"  {y}: {c}")

cur.close(); conn.close()
print('\nDone.')
