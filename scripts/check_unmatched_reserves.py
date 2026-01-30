#!/usr/bin/env python3
"""
Check the 257 calendar reserve numbers that didn't match charters.
Verify they actually exist in the charters table.
"""

import json
import psycopg2
import os

# Load the calendar JSON
with open('reports/outlook_calendar_arrow_new.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

appointments = data['appointments']
with_reserve = [a for a in appointments if a.get('reserve_number')]

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check each reserve number
unmatched = []
for appt in with_reserve:
    reserve_num = appt['reserve_number']
    
    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_num,))
    charter = cur.fetchone()
    
    if not charter:
        # Try with leading zeros normalized
        normalized = reserve_num.zfill(6)
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (normalized,))
        charter = cur.fetchone()
        
        if not charter:
            unmatched.append({
                'reserve_number': reserve_num,
                'normalized': normalized,
                'subject': appt.get('subject', ''),
                'location': appt.get('location', ''),
                'start_time': appt.get('start_time', '')
            })

print(f"Total appointments with reserve numbers: {len(with_reserve)}")
print(f"Unmatched reserve numbers: {len(unmatched)}")
print()

if unmatched:
    print("First 20 unmatched reserve numbers with FULL location field:")
    for item in unmatched[:20]:
        print(f"  Reserve: {item['reserve_number']}")
        print(f"    Location: {item['location']}")
        print(f"    Subject: {item['subject'][:60]}")
        print()
    
    # Check if these reserves exist at all in DB
    print("\nChecking if ANY of these reserve numbers exist in charters table:")
    sample_reserves = [item['reserve_number'] for item in unmatched[:10]]
    cur.execute(f"SELECT DISTINCT reserve_number FROM charters WHERE reserve_number IN ({','.join(['%s']*len(sample_reserves))})", sample_reserves)
    found = cur.fetchall()
    print(f"Found {len(found)} of the first 10 sample reserves in charters table: {found}")
    
    # Check for pattern issues
    print("\nReserve number patterns in unmatched:")
    patterns = {}
    for item in unmatched:
        rn = item['reserve_number']
        if rn.startswith('REF'):
            patterns['REF format'] = patterns.get('REF format', 0) + 1
        elif len(rn) == 6 and rn.isdigit():
            patterns['6-digit numeric'] = patterns.get('6-digit numeric', 0) + 1
        elif len(rn) == 5 and rn.isdigit():
            patterns['5-digit numeric'] = patterns.get('5-digit numeric', 0) + 1
        else:
            patterns['Other'] = patterns.get('Other', 0) + 1
    
    for pattern, count in patterns.items():
        print(f"  {pattern}: {count}")

cur.close()
conn.close()
