#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check cancelled charters pre-2025
cur.execute('''
SELECT COUNT(*) as cancelled_count, COALESCE(SUM(cc.amount), 0) as remaining_charges
FROM charters c
LEFT JOIN charter_charges cc ON cc.charter_id = c.charter_id
WHERE c.charter_date < '2025-01-01' AND c.status = 'cancelled'
''')
result = cur.fetchone()
print(f'✅ Cancelled pre-2025 charters: {result[0]}')
print(f'   Remaining charges: ${result[1]:,.2f}')

# Check unpaid charters with charges (excluding cancelled)
cur.execute('''
SELECT COUNT(DISTINCT c.charter_id) as unpaid_count, 
       COALESCE(SUM(ch.amount), 0) as total_charges
FROM charters c
LEFT JOIN charter_charges ch ON ch.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.charter_date < '2025-01-01'
  AND p.reserve_number IS NULL
  AND c.status NOT IN ('Cancelled', 'cancelled')
  AND ch.amount IS NOT NULL AND ch.amount > 0
''')
result = cur.fetchone()
if result[0]:
    print(f'\n⚠️  Unresolved pre-2025 unpaid charters: {result[0]}')
    print(f'   Total charges: ${result[1]:,.2f}')
else:
    print(f'\n✅ All pre-2025 unpaid charters resolved!')

cur.close()
conn.close()
