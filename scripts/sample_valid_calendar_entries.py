#!/usr/bin/env python3
"""
Sample valid calendar entries to understand the format better.
"""

import json

# Load the calendar JSON
with open('reports/outlook_calendar_arrow_new.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

appointments = data['appointments']
with_reserve = [a for a in appointments if a.get('reserve_number')]

# Sample entries with reserve numbers in the valid range (01000-020000)
print("Sample VALID calendar entries (reserve numbers 001000-020000):")
print()

valid_samples = [a for a in with_reserve if a.get('reserve_number') and 1000 <= int(a['reserve_number']) <= 20000]

for appt in valid_samples[:20]:
    print(f"Reserve: {appt['reserve_number']}")
    print(f"  Location: {appt.get('location', '(empty)')}")
    print(f"  Subject: {appt.get('subject', '(empty)')}")
    print(f"  Driver extracted: {appt.get('driver_name', '(none)')}")
    print()

print(f"\nTotal valid reserves (001000-020000): {len(valid_samples)}")
