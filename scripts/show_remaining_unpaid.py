#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Identify remaining unpaid charters
cur.execute('''
SELECT DISTINCT
    c.reserve_number,
    c.charter_date,
    c.status,
    COALESCE(c.notes, 'NULL') as notes,
    SUM(COALESCE(ch.amount, 0)) as charges
FROM charters c
LEFT JOIN charter_charges ch ON ch.charter_id = c.charter_id
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.charter_date < '2025-01-01'
  AND p.reserve_number IS NULL
  AND c.status NOT IN ('cancelled', 'Cancelled')
  AND ch.amount IS NOT NULL AND ch.amount > 0
GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.status, c.notes
ORDER BY c.charter_date DESC
''')

charters = cur.fetchall()
print(f"REMAINING {len(charters)} UNPAID PRE-2025 CHARTERS:\n")
for res, date, status, notes, charges in charters:
    notes_display = notes[:40] if notes != 'NULL' else '(no notes)'
    print(f"{res:6} {date} {status:20} {notes_display:42} ${charges:8,.2f}")

cur.close()
conn.close()
