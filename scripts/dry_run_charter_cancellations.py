#!/usr/bin/env python3
"""
Identify charters with no payments prior to 2025 for cancellation.
DRY-RUN: shows what will be cancelled, doesn't make changes.
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get charters with charges, no payments, prior to 2025
cur.execute('''
    SELECT 
        c.charter_id,
        c.reserve_number,
        c.charter_date,
        c.status,
        c.notes,
        SUM(COALESCE(cc.amount, 0)) as total_charges
    FROM charters c
    LEFT JOIN charter_charges cc ON c.charter_id = cc.charter_id
    WHERE c.reserve_number NOT IN (SELECT DISTINCT reserve_number FROM payments WHERE reserve_number IS NOT NULL)
    AND c.charter_date < '2025-01-01'
    AND cc.amount > 0
    AND c.notes NOT ILIKE '%trade%'
    AND c.notes NOT ILIKE '%gift%'
    AND c.notes NOT ILIKE '%promo%'
    AND c.status != 'Closed'
    AND c.status != 'closed_paid_verified'
    AND c.status != 'closed'
    GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.status, c.notes
    ORDER BY c.charter_date DESC
''')

to_cancel = cur.fetchall()
print(f"CHARTERS TO CANCEL (prior to 2025, with charges, no payments, not trade/gift):\n")
print(f"Total: {len(to_cancel)}")
print(f"{'Reserve':<10} {'Date':<12} {'Status':<20} {'Charges':<12}")
print("-" * 55)

total_charges_to_remove = 0
for charter_id, reserve, charter_date, status, notes, total_charges in to_cancel:
    print(f"{reserve:<10} {str(charter_date):<12} {(status or 'None'):<20} ${total_charges:>10,.2f}")
    total_charges_to_remove += total_charges

print("-" * 55)
print(f"\nTotal charges to delete: ${total_charges_to_remove:,.2f}")
print(f"\nTO APPLY THESE CHANGES, RUN: python apply_charter_cancellations.py --write")

cur.close()
conn.close()
