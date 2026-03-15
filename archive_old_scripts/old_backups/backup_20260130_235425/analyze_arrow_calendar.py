#!/usr/bin/env python3
"""
Analyze Arrow Limousine Calendar CSV for driver assignments and run history
"""

import csv
import re
from collections import defaultdict

# Open the calendar CSV
calendar_file = r'l:\limo\qb_storage\exports_verified\arrow limousine calender.CSV'

print("=" * 80)
print("ARROW LIMOUSINE CALENDAR ANALYSIS - DRIVER ASSIGNMENTS & RUN HISTORY")
print("=" * 80)

with open(calendar_file, 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.DictReader(f)
    
    # Clean up header names (remove BOM and quotes)
    fieldnames = [h.strip('\ufeff"') for h in reader.fieldnames]
    
    print(f"\n📋 CALENDAR FILE STRUCTURE:")
    print(f"   Total columns: {len(fieldnames)}")
    print(f"   Column names: {', '.join(fieldnames)}")
    
    # Reset to read data
    f.seek(0)
    next(f)  # Skip header
    reader = csv.reader(f)
    
    all_rows = list(reader)
    print(f"   Total calendar entries: {len(all_rows):,}")

print(f"\n" + "=" * 80)
print("SAMPLE CALENDAR ENTRIES (First 10):")
print("=" * 80)

with open(calendar_file, 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for i, row in enumerate(reader):
        if i >= 10:
            break
        
        subject = row[0].strip('"') if len(row) > 0 else ""
        start_date = row[1] if len(row) > 1 else ""
        start_time = row[2] if len(row) > 2 else ""
        categories = row[14] if len(row) > 14 else ""
        description = row[15] if len(row) > 15 else ""
        location = row[16] if len(row) > 16 else ""
        
        print(f"\n📅 Entry #{i+1}:")
        print(f"   Subject: {subject[:120]}")
        print(f"   Date/Time: {start_date} {start_time}")
        print(f"   Categories: {categories[:80]}")
        print(f"   Location: {location[:80]}")
        if description:
            print(f"   Description: {description[:150]}")

print(f"\n" + "=" * 80)
print("ANALYZING FOR DRIVER INFORMATION:")
print("=" * 80)

# Patterns to look for driver names
driver_patterns = [
    r'driver[:\s]+([A-Za-z\s]+)',
    r'Dr\d+',  # Driver codes like Dr09
    r'assigned[:\s]+([A-Za-z\s]+)',
    r'chauffeur[:\s]+([A-Za-z\s]+)',
]

driver_mentions = defaultdict(int)
reserve_number_refs = []
entries_with_drivers = []

with open(calendar_file, 'r', encoding='utf-8', errors='ignore') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    
    for i, row in enumerate(reader):
        subject = row[0].strip('"') if len(row) > 0 else ""
        description = row[15] if len(row) > 15 else ""
        categories = row[14] if len(row) > 14 else ""
        
        # Combine all text fields
        full_text = f"{subject} {description} {categories}"
        
        # Look for driver mentions
        for pattern in driver_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            for match in matches:
                driver_mentions[match] += 1
                
        # Look for reserve numbers
        reserve_matches = re.findall(r'\b\d{6}\b', full_text)
        if reserve_matches:
            reserve_number_refs.extend(reserve_matches)
        
        # Track entries that might have driver info
        if any(keyword in full_text.lower() for keyword in ['driver', 'dr0', 'dr1', 'chauffeur', 'assigned']):
            entries_with_drivers.append({
                'index': i,
                'subject': subject[:100],
                'date': row[1] if len(row) > 1 else "",
                'text': full_text[:200]
            })

print(f"\n🚗 DRIVER MENTIONS FOUND:")
if driver_mentions:
    for driver, count in sorted(driver_mentions.items(), key=lambda x: x[1], reverse=True)[:20]:
        print(f"   {driver}: {count} times")
else:
    print("   No explicit driver mentions found")

print(f"\n📋 RESERVE NUMBER REFERENCES:")
if reserve_number_refs:
    unique_reserves = set(reserve_number_refs)
    print(f"   Total reserve number mentions: {len(reserve_number_refs)}")
    print(f"   Unique reserve numbers: {len(unique_reserves)}")
    print(f"   Sample: {sorted(list(unique_reserves))[:10]}")
else:
    print("   No reserve numbers found")

print(f"\n🔍 ENTRIES WITH POTENTIAL DRIVER INFO:")
print(f"   Total entries: {len(entries_with_drivers)}")

if entries_with_drivers:
    print("\n   Sample entries with driver references:")
    for entry in entries_with_drivers[:10]:
        print(f"\n   Entry #{entry['index']+1} ({entry['date']}):")
        print(f"      Subject: {entry['subject']}")
        print(f"      Content: {entry['text']}")

print(f"\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)
print(f"""
The Arrow calendar CSV appears to be an Outlook calendar export containing
{len(all_rows):,} calendar entries from the limousine booking/dispatch system.

Key Findings:
- Driver mentions: {len(driver_mentions)} unique patterns found
- Reserve number references: {len(set(reserve_number_refs))} unique
- Entries with driver info: {len(entries_with_drivers)}

This calendar may contain:
1. Scheduled pickups/dropoffs with driver assignments
2. Dispatch notes and run information
3. Customer appointment details
4. Driver schedule tracking

Recommendation: Parse this calendar data and link entries to charters table
using reserve numbers, dates, and customer names to extract driver assignment
history that LMS didn't track.
""")
