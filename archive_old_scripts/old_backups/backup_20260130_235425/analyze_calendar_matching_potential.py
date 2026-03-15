import json
import psycopg2
import os
from datetime import datetime
import re

# Load calendar events
with open('reports/calendar_0_events.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

events = data['events']

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Get all charter dates
cur.execute("SELECT charter_date, COUNT(*) FROM charters GROUP BY charter_date ORDER BY charter_date")
charter_dates = {row[0]: row[1] for row in cur.fetchall()}

# Analyze calendar events
stats = {
    'total_events': len(events),
    'with_reserve_numbers': 0,
    'with_extracted_dates': 0,
    'with_meaningful_subjects': 0,
    'matching_charter_dates': 0,
    'single_charter_per_date': 0
}

events_by_date = {}

for event in events:
    # Check for reserve numbers
    reserve_pattern = r'\b(\d{6})\b'
    all_text = (event.get('subject', '') + ' ' + 
                event.get('body', '') + ' ' + 
                event.get('location', ''))
    found_reserves = re.findall(reserve_pattern, all_text)
    
    if found_reserves:
        stats['with_reserve_numbers'] += 1
    
    # Check for extracted dates from IMAP failures
    if 'Sent date:' in event.get('body', ''):
        match = re.search(r'Sent date:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', event.get('body', ''))
        if match:
            stats['with_extracted_dates'] += 1
            try:
                date_str = match.group(1)
                dt = datetime.strptime(date_str, '%m/%d/%Y %H:%M:%S')
                date_key = dt.date()
                
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                events_by_date[date_key].append(event)
                
                # Check if this date has charters
                if date_key in charter_dates:
                    stats['matching_charter_dates'] += 1
                    if charter_dates[date_key] == 1:
                        stats['single_charter_per_date'] += 1
            except:
                pass
    
    # Check for meaningful subjects
    subject = event.get('subject', '')
    if 'Subject: "' in event.get('body', ''):
        match = re.search(r'Subject:\s*"([^"]+)"', event.get('body', ''))
        if match:
            subject = match.group(1)
    
    if subject and len(subject) > 10 and 'IMAP' not in subject:
        stats['with_meaningful_subjects'] += 1

# Print statistics
print("=" * 80)
print("CALENDAR EVENTS ANALYSIS")
print("=" * 80)
print(f"Total calendar events:              {stats['total_events']:,}")
print(f"Events with reserve numbers:        {stats['with_reserve_numbers']:,}")
print(f"Events with extracted dates:        {stats['with_extracted_dates']:,}")
print(f"Events with meaningful subjects:    {stats['with_meaningful_subjects']:,}")
print(f"Events matching charter dates:      {stats['matching_charter_dates']:,}")
print(f"  - With single charter on date:    {stats['single_charter_per_date']:,}")
print()
print(f"Dates with calendar events:         {len(events_by_date):,}")
print(f"Dates with charters in DB:          {len(charter_dates):,}")

# Sample events that could be matched
print("\n" + "=" * 80)
print("SAMPLE MATCHABLE EVENTS (no reserve #, single charter on date):")
print("=" * 80)

sample_count = 0
for date_key, date_events in sorted(events_by_date.items())[:20]:
    if date_key in charter_dates and charter_dates[date_key] == 1:
        for event in date_events:
            # Extract subject
            subject = event.get('subject', '')
            if 'Subject: "' in event.get('body', ''):
                match = re.search(r'Subject:\s*"([^"]+)"', event.get('body', ''))
                if match:
                    subject = match.group(1)
            
            # Check if no reserve number
            reserve_pattern = r'\b(\d{6})\b'
            all_text = subject + ' ' + event.get('location', '')
            if not re.findall(reserve_pattern, all_text):
                print(f"{date_key}: {subject[:60]}")
                sample_count += 1
                if sample_count >= 10:
                    break
    
    if sample_count >= 10:
        break

cur.close()
conn.close()
