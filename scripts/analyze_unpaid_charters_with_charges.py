#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Charters with no payments
cur.execute('''SELECT COUNT(*) FROM charters WHERE reserve_number NOT IN (SELECT DISTINCT reserve_number FROM payments WHERE reserve_number IS NOT NULL)''')
total_unpaid = cur.fetchone()[0]

# Charters with no payments but have positive charges
cur.execute('''
    SELECT COUNT(*), SUM(cc.amount)
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    WHERE c.reserve_number NOT IN (SELECT DISTINCT reserve_number FROM payments WHERE reserve_number IS NOT NULL)
    AND cc.amount > 0
''')
count_with_charges, total_charges = cur.fetchone()

# Break down by status
cur.execute('''
    SELECT c.status, COUNT(*), SUM(COALESCE(cc.amount, 0))
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    WHERE c.reserve_number NOT IN (SELECT DISTINCT reserve_number FROM payments WHERE reserve_number IS NOT NULL)
    AND cc.amount > 0
    GROUP BY c.status
    ORDER BY COUNT(*) DESC
''')
status_breakdown = cur.fetchall()

print(f"Charters with NO payments: {total_unpaid:,}")
print(f"  - With positive charges: {count_with_charges:,}")
print(f"  - Total charges amount: ${total_charges:,.2f}" if total_charges else "  - Total charges: $0.00")
print(f"\nBreakdown by status:")
for status, cnt, amt in status_breakdown:
    print(f"  {status}: {cnt:,} charters, ${amt:,.2f}")

cur.close()
conn.close()
