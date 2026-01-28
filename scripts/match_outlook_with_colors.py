#!/usr/bin/env python3
"""
Match Outlook calendar to charters with color-coded status (replaces Excel report).
Matches by reserve_number and assigns visual color indicators:
- Green: Perfect match
- Red: Not in calendar
- Yellow: Data mismatch
- Blue: Recently updated
- Gray: Cancelled
"""

import json
import sys
import os
import argparse
from datetime import datetime
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def normalize_name(text):
    """Normalize name for comparison."""
    if not text:
        return ""
    return ' '.join(text.lower().split())


def driver_matches(calendar_driver, db_driver):
    """Check if driver names match (fuzzy)."""
    if not calendar_driver or not db_driver:
        return True  # Don't flag as mismatch if one is missing
    
    cal_norm = normalize_name(calendar_driver)
    db_norm = normalize_name(db_driver)
    
    # Exact match
    if cal_norm == db_norm:
        return True
    
    # First name match
    cal_first = cal_norm.split()[0] if cal_norm else ""
    db_first = db_norm.split()[0] if db_norm else ""
    
    if cal_first and db_first and cal_first == db_first:
        return True
    
    return False


def build_mismatch_note(appointment, charter):
    """Build detailed mismatch description."""
    mismatches = []
    
    cal_driver = appointment.get('driver_name', '')
    db_driver = charter.get('driver_name', '')
    
    if cal_driver and db_driver and not driver_matches(cal_driver, db_driver):
        mismatches.append(f"Driver: Calendar={cal_driver}, DB={db_driver}")
    
    cal_location = appointment.get('location', '')
    db_location = f"{charter['reserve_number']} {charter.get('driver_name', '')}".strip()
    
    if cal_location and normalize_name(cal_location) != normalize_name(db_location):
        mismatches.append(f"Location differs: {cal_location}")
    
    # Check for cancellation flag in calendar
    for field in ['location', 'subject', 'body', 'categories']:
        text = str(appointment.get(field, '')).lower()
        if 'cancel' in text:
            mismatches.append(f"Cancellation detected in calendar {field}")
            break
    
    if mismatches:
        return " | ".join(mismatches)
    else:
        return None


def match_with_color_coding(calendar_json, year=2026, apply_colors=False):
    """
    Match calendar to charters and apply color coding.
    Returns statistics about sync status.
    """
    
    print(f"=" * 70)
    print(f"OUTLOOK CALENDAR SYNC WITH COLOR CODING - {year}")
    print(f"Mode: {'APPLY COLORS (database update)' if apply_colors else 'DRY RUN (preview only)'}")
    print(f"=" * 70)
    
    # Load calendar data
    print(f"\nLoading calendar data from {calendar_json}...")
    with open(calendar_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    appointments = data.get('appointments', [])
    
    # Filter to specified year
    year_appointments = []
    for appt in appointments:
        start_date = appt.get('start_date')
        if start_date and start_date.startswith(str(year)):
            year_appointments.append(appt)
    
    print(f"Loaded {len(year_appointments)} appointments for {year}")
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get all charters for the year
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date,
               c.driver_name, c.client_display_name, c.total_amount_due,
               c.paid_amount, c.status,
               v.vehicle_number
        FROM charters c
        LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
        WHERE EXTRACT(YEAR FROM c.charter_date) = %s
        ORDER BY c.charter_date
    """, (year,))
    
    columns = [desc[0] for desc in cur.description]
    charters_list = [dict(zip(columns, row)) for row in cur.fetchall()]
    
    # Build lookup dictionary
    charters_dict = {c['reserve_number']: c for c in charters_list}
    
    print(f"Loaded {len(charters_dict)} charters from database\n")
    
    # Statistics
    stats = {
        'green': 0,  # Perfect match
        'yellow': 0,  # Mismatch
        'red': 0,    # Not in calendar
        'gray': 0,   # Cancelled
        'blue': 0    # Updated
    }
    
    matched_reserves = set()
    
    print("Processing appointments...\n")
    
    # Process each appointment
    for appt in year_appointments:
        reserve_num = appt.get('reserve_number')
        
        if not reserve_num:
            continue
        
        if reserve_num not in charters_dict:
            # Appointment exists but no matching charter - skip
            continue
        
        charter = charters_dict[reserve_num]
        matched_reserves.add(reserve_num)
        
        # Check for cancellation
        if charter.get('status') == 'cancelled':
            color = 'gray'
            status = 'cancelled'
            notes = 'Cancelled charter'
            stats['gray'] += 1
        
        # Check for mismatches
        elif not driver_matches(appt.get('driver_name'), charter.get('driver_name')):
            color = 'yellow'
            status = 'mismatch'
            notes = build_mismatch_note(appt, charter)
            stats['yellow'] += 1
        
        else:
            # Perfect match
            color = 'green'
            status = 'synced'
            notes = 'Synced and matched'
            stats['green'] += 1
        
        # Update charter
        if apply_colors:
            cur.execute("""
                UPDATE charters
                SET calendar_sync_status = %s,
                    calendar_color = %s,
                    calendar_notes = %s
                WHERE reserve_number = %s
            """, (status, color, notes, reserve_num))
    
    # Mark charters NOT in calendar as RED
    for reserve_num, charter in charters_dict.items():
        if reserve_num not in matched_reserves:
            if charter.get('status') == 'cancelled':
                color = 'gray'
                status = 'cancelled'
                notes = 'Cancelled - not in calendar'
                stats['gray'] += 1
            else:
                color = 'red'
                status = 'not_in_calendar'
                notes = 'Missing from Outlook calendar'
                stats['red'] += 1
            
            if apply_colors:
                cur.execute("""
                    UPDATE charters
                    SET calendar_sync_status = %s,
                        calendar_color = %s,
                        calendar_notes = %s
                    WHERE reserve_number = %s
                """, (status, color, notes, reserve_num))
    
    if apply_colors:
        conn.commit()
        print("✓ Database updated with color codes\n")
    else:
        print("DRY RUN - No database changes made\n")
    
    # Print summary
    print("=" * 70)
    print("SYNC STATUS SUMMARY:")
    print("=" * 70)
    print(f"🟢 Green (Synced):          {stats['green']:4d} charters")
    print(f"🔴 Red (Not in Calendar):   {stats['red']:4d} charters")
    print(f"🟡 Yellow (Mismatch):       {stats['yellow']:4d} charters")
    print(f"🔵 Blue (Updated):          {stats['blue']:4d} charters")
    print(f"⚫ Gray (Cancelled):        {stats['gray']:4d} charters")
    print("=" * 70)
    print(f"Total charters:             {len(charters_dict):4d}")
    print(f"Matched from calendar:      {len(matched_reserves):4d}")
    print(f"Match rate:                 {len(matched_reserves)/len(charters_dict)*100:.1f}%")
    print("=" * 70)
    
    if not apply_colors:
        print("\nRun with --apply-colors to update database")
    
    # Show examples of each color
    print("\nSample charters by status:")
    print("-" * 70)
    
    for color_name, color_code in [('Green', 'green'), ('Red', 'red'), ('Yellow', 'yellow')]:
        examples = [c for c in charters_list if c['reserve_number'] in matched_reserves or color_code == 'red']
        
        if color_code == 'green':
            examples = [c for c in charters_list if c['reserve_number'] in matched_reserves]
            examples = examples[:3]
        elif color_code == 'red':
            examples = [c for c in charters_list if c['reserve_number'] not in matched_reserves]
            examples = examples[:3]
        elif color_code == 'yellow':
            examples = []  # Would need mismatch detection here
        
        if examples:
            print(f"\n{color_name} examples:")
            for charter in examples:
                client = charter.get('client_display_name') or charter.get('client_name') or 'Unknown'
                print(f"  {charter['charter_date']} - {charter['reserve_number']} - {client}")
    
    cur.close()
    conn.close()
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Match Outlook calendar with color coding')
    parser.add_argument('--input', default='reports/outlook_calendar_arrow_new.json',
                        help='Input JSON file from extract_outlook_calendar.py')
    parser.add_argument('--year', type=int, default=2026,
                        help='Year to process (default: 2026)')
    parser.add_argument('--apply-colors', action='store_true',
                        help='Update database with color codes (default: dry-run)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"ERROR: Calendar file not found: {args.input}")
        print("\nRun this first:")
        print(f"  python scripts/extract_outlook_calendar.py --calendar 'arrow new' --output {args.input}")
        sys.exit(1)
    
    match_with_color_coding(args.input, year=args.year, apply_colors=args.apply_colors)


if __name__ == '__main__':
    main()
