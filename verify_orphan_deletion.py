#!/usr/bin/env python3
"""Verify orphaned payments deletion."""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

# Verify no orphaned payments remain
cur.execute('''
    SELECT COUNT(*) AS orphaned_count, 
           EXTRACT(YEAR FROM p.payment_date) AS year
    FROM payments p
    WHERE p.reserve_number IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM charters c WHERE c.reserve_number = p.reserve_number
      )
    GROUP BY EXTRACT(YEAR FROM p.payment_date)
    ORDER BY year DESC
''')

orphaned = cur.fetchall()
if orphaned:
    print('⚠️ Remaining orphaned payments:')
    for count, year in orphaned:
        year_str = int(year) if year else "NULL"
        print(f'  Year {year_str}: {count} payments')
else:
    print('✅ No orphaned payments remaining!')

# Show payment count before/after context
cur.execute('SELECT COUNT(*) FROM payments')
total = cur.fetchone()[0]
print(f'\n📊 Total payments in database: {total}')

cur.execute('''
    SELECT COUNT(*) FROM payments 
    WHERE EXTRACT(YEAR FROM payment_date) >= 2025
''')
recent = cur.fetchone()[0]
print(f'📊 2025-2026 payments: {recent}')

# Show backup table info
cur.execute('''
    SELECT COUNT(*) FROM payments_backup_20260110_025229
''')
backup_count = cur.fetchone()[0]
print(f'\n💾 Backup table (payments_backup_20260110_025229): {backup_count} rows preserved')

cur.close()
conn.close()
