#!/usr/bin/env python3
"""Check email E-Transfer received events structure and data"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check for received e-transfers
cur.execute("""
    SELECT 
        event_type,
        COUNT(*) as count,
        SUM(amount) as total_amount,
        MIN(email_date) as earliest,
        MAX(email_date) as latest
    FROM email_financial_events
    WHERE source LIKE '%etransfer%'
    GROUP BY event_type
    ORDER BY count DESC
""")

print("\nE-Transfer Events by Type:")
print("-" * 80)
print(f"{'Type':<30} {'Count':<10} {'Amount':<15} {'Date Range'}")
print("-" * 80)
for evt_type, count, amt, earliest, latest in cur.fetchall():
    date_range = f"{earliest} to {latest}" if earliest and latest else ""
    print(f"{evt_type:<30} {count:<10,} ${amt or 0:<14,.2f} {date_range}")

# Check for received with notes (might have reserve number)
cur.execute("""
    SELECT 
        email_date,
        amount,
        notes,
        subject
    FROM email_financial_events
    WHERE event_type LIKE '%received%'
    AND notes IS NOT NULL
    ORDER BY email_date DESC
    LIMIT 10
""")

print("\n\nSample RECEIVED E-Transfers with Notes:")
print("-" * 80)
for email_date, amt, notes, subject in cur.fetchall():
    notes_short = (notes or '')[:60]
    print(f"{email_date} | ${amt:>10,.2f} | {notes_short}")

# Check if there's a separate table for e-transfer details
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    AND table_name LIKE '%transfer%'
    ORDER BY table_name
""")

print("\n\nTables with 'transfer' in name:")
print("-" * 50)
for (tname,) in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM {tname}")
    count = cur.fetchone()[0]
    print(f"  {tname:<40} {count:>10,} rows")

cur.close()
conn.close()
