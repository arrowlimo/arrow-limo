#!/usr/bin/env python3
import json

with open('reports/outlook_calendar_arrow_new.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

appointments = data['appointments']

# Find appointments with cancel/cancelled keywords
cancelled = []
for appt in appointments:
    subject = str(appt.get('subject', '')).lower()
    body = str(appt.get('body', '')).lower()
    location = str(appt.get('location', '')).lower()
    categories = str(appt.get('categories', '')).lower()
    
    if any('cancel' in text for text in [subject, body, location, categories]):
        cancelled.append(appt)

print(f"Total appointments: {len(appointments)}")
print(f"With 'cancel' keyword: {len(cancelled)}")

# Group by those with reserve numbers
with_reserve = [a for a in cancelled if a.get('reserve_number')]
without_reserve = [a for a in cancelled if not a.get('reserve_number')]

print(f"\nWith reserve numbers: {len(with_reserve)}")
print(f"Without reserve numbers: {len(without_reserve)}")

print(f"\n=== Sample Cancelled Appointments (with reserve) ===")
for appt in with_reserve[:15]:
    reserve = appt.get('reserve_number', 'NO_RES')
    subject = appt.get('subject', '')[:70]
    location = appt.get('location', '')
    print(f"  {reserve}: {subject}")
    if 'cancel' in location.lower():
        print(f"    Location: {location}")

print(f"\n=== Keywords Found ===")
keywords = {}
for appt in cancelled:
    for field in ['subject', 'body', 'location', 'categories']:
        text = str(appt.get(field, '')).lower()
        if 'cancel' in text:
            if field not in keywords:
                keywords[field] = 0
            keywords[field] += 1

for field, count in keywords.items():
    print(f"  {field}: {count}")
