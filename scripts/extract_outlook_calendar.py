#!/usr/bin/env python3
"""
Extract Outlook calendar data via COM automation.
Finds the 'arrow new' calendar folder and extracts all appointments with:
- Subject, body, start/end times, location, notes
- Parsed reserve number and driver name
- Outputs to JSON for matching against almsdata charters
"""

import win32com.client
import pythoncom
import json
import re
import sys
from datetime import datetime
import argparse
import re


def extract_reserve_number(text):
    """Extract reserve number from text: strictly 6 digits starting with 0."""
    if not text:
        return None

    # Only accept 6-digit values that start with 0 (e.g., 019708)
    match = re.search(r'\b(0\d{5})\b', text)
    if match:
        return match.group(1)

    # Do not accept REF or 5-digit fallbacks anymore to avoid false positives
    return None


def extract_phone_numbers(text):
    """Extract phone numbers from text."""
    if not text:
        return []
    
    # Pattern for various phone formats
    phones = re.findall(r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})', text)
    return [f"({area}) {prefix}-{line}" for area, prefix, line in phones]


def extract_passenger_info(text):
    """Extract passenger count or names from text."""
    if not text:
        return None
    
    # Try to find passenger count
    match = re.search(r'(\d+)\s*(?:passenger|pax|people|guests?)', text, re.IGNORECASE)
    if match:
        return {"count": int(match.group(1))}
    
    return None


def extract_emails(text):
    """Extract email addresses from free text."""
    if not text:
        return []
    # Basic RFC-like pattern suitable for calendar notes
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Za-z]{2,}"
    emails = re.findall(pattern, text)
    # Normalize and dedupe
    seen = set()
    out = []
    for e in emails:
        el = e.strip().lower()
        if el not in seen:
            seen.add(el)
            out.append(el)
    return out


def extract_driver_name(text):
    """Extract driver name from text using common patterns."""
    if not text:
        return None
    
    # Pattern 1: Location field format "019708 John" or "019708-John" or "019708 - John"
    # Extract first name after reserve number
    match = re.search(r'\b0\d{5}\s*[-\s]*([A-Za-z]+)', text)
    if match:
        name = match.group(1).strip()
        if len(name) > 1 and len(name) < 30:
            return name
    
    # Pattern 2: "Driver: John Smith" or "Driver - John Smith" or "driver:john smith"
    match = re.search(r'(?:driver|chauffeur)\s*[:\-]\s*([A-Za-z\s]+?)(?:\n|$|,|\|)', text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        # Clean up extra whitespace
        name = ' '.join(name.split())
        if len(name) > 2 and len(name) < 50:  # Reasonable name length
            return name
    
    # Pattern 3: Just a name at the start or after punctuation
    # "John Smith" or "John" 
    match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text)
    if match:
        name = match.group(1).strip()
        if len(name) > 2 and len(name) < 50:
            return name
    
    return None


def find_calendar_folder(outlook, folder_name):
    """Recursively find a calendar folder by name."""
    namespace = outlook.GetNamespace("MAPI")
    
    def search_folders(folder):
        """Recursively search folders."""
        # Check current folder
        if folder.Name.lower() == folder_name.lower():
            # Verify it's a calendar folder (olFolderCalendar = 9)
            if folder.DefaultItemType == 1:  # olAppointmentItem = 1
                return folder
        
        # Search subfolders
        try:
            for subfolder in folder.Folders:
                result = search_folders(subfolder)
                if result:
                    return result
        except:
            pass
        
        return None
    
    # Start with default calendar and its parent
    try:
        default_calendar = namespace.GetDefaultFolder(9)  # olFolderCalendar = 9
        
        # Check default calendar first
        if default_calendar.Name.lower() == folder_name.lower():
            return default_calendar
        
        # Search in default calendar's parent (usually the mailbox root)
        result = search_folders(default_calendar.Parent)
        if result:
            return result
        
        # Search entire mailbox
        for folder in namespace.Folders:
            result = search_folders(folder)
            if result:
                return result
    except Exception as e:
        print(f"Error searching folders: {e}", file=sys.stderr)
    
    return None


def merge_split_reservations(appointments):
    """
    Merge calendar entries that are split across midnight but represent the same charter.
    Groups by reserve_number and merges consecutive entries.
    """
    if not appointments:
        return []
    
    # Group by reserve number
    by_reserve = {}
    for appt in appointments:
        reserve = appt.get('reserve_number')
        if reserve:
            if reserve not in by_reserve:
                by_reserve[reserve] = []
            by_reserve[reserve].append(appt)
    
    # Merge splits for each reserve number
    merged = []
    processed_indices = set()
    
    for i, appt in enumerate(appointments):
        if i in processed_indices:
            continue
        
        reserve = appt.get('reserve_number')
        if not reserve or len(by_reserve.get(reserve, [])) <= 1:
            # Single entry, keep as-is
            merged.append(appt)
            processed_indices.add(i)
            continue
        
        # Check if this is part of a split (consecutive entries with same reserve)
        group = [appt]
        group_indices = [i]
        
        # Look ahead for consecutive entries with same reserve
        for j in range(i + 1, len(appointments)):
            if j in processed_indices:
                continue
            
            next_appt = appointments[j]
            if next_appt.get('reserve_number') == reserve:
                # Check if times are consecutive (within 2 hours)
                try:
                    if appt.get('end_time') and next_appt.get('start_time'):
                        end_dt = datetime.strptime(appt['end_time'], '%Y-%m-%d %H:%M:%S')
                        next_start_dt = datetime.strptime(next_appt['start_time'], '%Y-%m-%d %H:%M:%S')
                        time_gap = (next_start_dt - end_dt).total_seconds() / 3600
                        
                        if time_gap <= 2:  # Within 2 hours = likely split
                            group.append(next_appt)
                            group_indices.append(j)
                            appt = next_appt  # Update for next iteration
                        else:
                            break  # Gap too large, separate booking
                    else:
                        break
                except:
                    break
            else:
                break
        
        # Mark all as processed
        for idx in group_indices:
            processed_indices.add(idx)
        
        if len(group) > 1:
            # Merge the group
            merged_appt = {
                'subject': group[0]['subject'],
                'body': '\n\n--- MERGED FROM SPLIT ENTRIES ---\n\n'.join(g['body'] for g in group if g.get('body')),
                'location': group[0]['location'],
                'start_time': group[0]['start_time'],  # First start
                'end_time': group[-1]['end_time'],      # Last end
                'reserve_number': reserve,
                'driver_name': group[0]['driver_name'],
                'all_day_event': any(g.get('all_day_event') for g in group),
                'categories': group[0].get('categories', ''),
                'organizer': group[0].get('organizer', ''),
                'phone_numbers': [],
                'passenger_info': None,
                'is_merged': True,
                'merged_count': len(group)
            }
            
            # Collect all phone numbers from all parts
            for g in group:
                phones = extract_phone_numbers(g.get('body', '') + ' ' + g.get('subject', ''))
                merged_appt['phone_numbers'].extend(phones)
            merged_appt['phone_numbers'] = list(set(merged_appt['phone_numbers']))  # Dedupe
            
            # Get passenger info from any part
            for g in group:
                passenger_info = extract_passenger_info(g.get('body', ''))
                if passenger_info:
                    merged_appt['passenger_info'] = passenger_info
                    break
            
            merged.append(merged_appt)
        else:
            # Single entry, add extra details
            appt['phone_numbers'] = extract_phone_numbers(appt.get('body', '') + ' ' + appt.get('subject', ''))
            appt['passenger_info'] = extract_passenger_info(appt.get('body', ''))
            appt['is_merged'] = False
            appt['merged_count'] = 1
            merged.append(appt)
    
    return merged


def extract_calendar_data(calendar_name='arrow new', output_file='outlook_calendar.json'):
    """Extract all appointments from specified Outlook calendar."""
    pythoncom.CoInitialize()
    
    try:
        # Connect to Outlook
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        
        print(f"Connected to Outlook")
        
        # Find the target calendar
        calendar = find_calendar_folder(outlook, calendar_name)
        
        if not calendar:
            print(f"ERROR: Calendar folder '{calendar_name}' not found")
            print("\nAvailable calendar folders:")
            
            # List available calendars
            default_cal = namespace.GetDefaultFolder(9)  # olFolderCalendar
            print(f"  - {default_cal.Name} (default)")
            
            def list_calendars(folder, indent=2):
                try:
                    for subfolder in folder.Folders:
                        if subfolder.DefaultItemType == 1:  # Calendar
                            print(f"  {' ' * indent}- {subfolder.Name}")
                        list_calendars(subfolder, indent + 2)
                except:
                    pass
            
            list_calendars(default_cal.Parent)
            return False
        
        print(f"Found calendar: {calendar.Name}")
        print(f"Extracting appointments...")
        
        # Get all appointments
        items = calendar.Items
        items.Sort("[Start]")  # Sort by start time
        items.IncludeRecurrences = True  # Include recurring appointments
        
        appointments = []
        total_count = items.Count
        
        print(f"Processing {total_count} appointments...")
        
        for idx, item in enumerate(items, 1):
            if idx % 100 == 0:
                print(f"  Processed {idx}/{total_count}...")
            
            try:
                # Extract basic fields
                subject = item.Subject or ""
                body = item.Body or ""
                location = item.Location or ""
                
                # Parse start/end times
                start_time = None
                end_time = None
                start_date = None
                end_date = None
                
                try:
                    if item.Start:
                        start_time = item.Start.strftime('%Y-%m-%d %H:%M:%S')
                        start_date = item.Start.strftime('%Y-%m-%d')
                except:
                    pass
                
                try:
                    if item.End:
                        end_time = item.End.strftime('%Y-%m-%d %H:%M:%S')
                        end_date = item.End.strftime('%Y-%m-%d')
                except:
                    pass
                
                # Parse reserve number - CHECK LOCATION FIRST (that's where it usually is!)
                reserve_number = extract_reserve_number(location)
                if not reserve_number:
                    reserve_number = extract_reserve_number(subject)
                if not reserve_number:
                    reserve_number = extract_reserve_number(body)
                
                # Parse driver name - CHECK LOCATION FIRST (driver first name usually there)
                driver_name = extract_driver_name(location)
                if not driver_name:
                    driver_name = extract_driver_name(subject)
                if not driver_name:
                    driver_name = extract_driver_name(body)
                
                # Extract additional details
                phone_numbers = extract_phone_numbers(body + ' ' + subject)
                emails = extract_emails(body + ' ' + subject)
                passenger_info = extract_passenger_info(body)
                
                # Get additional Outlook fields
                importance = getattr(item, 'Importance', 1)  # 0=Low, 1=Normal, 2=High
                reminder_set = getattr(item, 'ReminderSet', False)
                
                # Build appointment record
                appointment = {
                    'subject': subject,
                    'body': body,
                    'location': location,
                    'start_time': start_time,
                    'end_time': end_time,
                    'start_date': start_date,
                    'end_date': end_date,
                    'reserve_number': reserve_number,
                    'driver_name': driver_name,
                    'phone_numbers': phone_numbers,
                    'passenger_info': passenger_info,
                    'emails': emails,
                    'all_day_event': item.AllDayEvent,
                    'categories': item.Categories or "",
                    'organizer': getattr(item, 'Organizer', ''),
                    'importance': importance,
                    'reminder_set': reminder_set,
                    'is_merged': False,
                    'merged_count': 1
                }
                
                appointments.append(appointment)
                
            except Exception as e:
                print(f"  Warning: Error processing item {idx}: {e}", file=sys.stderr)
                continue
        
        print(f"\nExtracted {len(appointments)} raw appointments")
        
        # Merge split reservations
        print(f"Merging split reservations (past midnight)...")
        appointments = merge_split_reservations(appointments)
        
        print(f"After merging: {len(appointments)} appointments")
        
        # Count parsed data
        with_reserve = sum(1 for a in appointments if a['reserve_number'])
        with_driver = sum(1 for a in appointments if a['driver_name'])
        with_times = sum(1 for a in appointments if a['start_time'] and a['end_time'])
        merged_count = sum(1 for a in appointments if a.get('is_merged'))
        
        print(f"  - {with_reserve} with reserve numbers")
        print(f"  - {with_driver} with driver names")
        print(f"  - {with_times} with start/end times")
        print(f"  - {merged_count} merged from split entries")
        
        # Save to JSON
        output = {
            'extraction_date': datetime.now().isoformat(),
            'calendar_name': calendar_name,
            'total_appointments': len(appointments),
            'merged_appointments': merged_count,
            'appointments': appointments
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        pythoncom.CoUninitialize()


def main():
    parser = argparse.ArgumentParser(description='Extract Outlook calendar data via COM')
    parser.add_argument('--calendar', default='arrow new',
                        help='Calendar folder name (default: "arrow new")')
    parser.add_argument('--output', default='reports/outlook_calendar_arrow_new.json',
                        help='Output JSON file path')
    
    args = parser.parse_args()
    
    success = extract_calendar_data(args.calendar, args.output)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
