import os
import sys
import json
import psycopg2
from datetime import datetime, timedelta
import re

"""
Match Calendar Events to Reservations and Update Dispatch Notes
-----------------------------------------------------------------
Purpose:
  1. Load calendar events from JSON (Calendar_0)
  2. Match events to charters by reserve_number and/or date/time overlap
  3. Update charters.booking_notes with calendar event details
  4. Skip IMAP retrieval failure bodies (contaminated data)
  5. Support dry-run mode for safety

Matching Strategy:
  - Primary: Exact reserve_number match in event subject/body
  - Secondary: Date/time overlap (charter_date ±1 day, pickup_time overlap)
  - Skip: Events with no reserve numbers and no valid dates
  
Output Handling:
  - Skip events with IMAP failure bodies
  - Format: "📅 Calendar Event: {subject}\n📍 Location: {location}\n⏰ Time: {start} to {end}\n📝 Details: {body}"
  - Only update if booking_notes is empty OR --force-overwrite flag
  - Always preserve existing notes unless forced

Usage:
  python -X utf8 scripts/match_calendar_to_reservations.py [--apply] [--force-overwrite] [--show-preview]
  
  --apply: Actually write updates to database (default is dry-run)
  --force-overwrite: Overwrite existing booking_notes (default: skip if not empty)
  --show-preview: Display formatted notes before applying

Environment Variables:
  DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
"""

def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )
    return conn

def is_imap_failure(body):
    """Detect IMAP retrieval failure stub bodies."""
    if not body:
        return False
    failure_markers = [
        "Retrieval using the IMAP4 protocol failed",
        "The server couldn't retrieve the following message",
        "The message hasn't been deleted"
    ]
    return any(marker in body for marker in failure_markers)

def extract_useful_subject_from_imap_failure(body):
    """Extract original subject from IMAP failure message."""
    if not body:
        return None
    # Pattern: Subject: "original subject text"
    match = re.search(r'Subject:\s*"([^"]+)"', body)
    if match:
        return match.group(1)
    return None

def extract_sent_date_from_imap_failure(body):
    """Extract sent date from IMAP failure message."""
    if not body:
        return None
    # Pattern: Sent date: MM/DD/YYYY HH:MM:SS
    match = re.search(r'Sent date:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', body)
    if match:
        try:
            # Parse date string
            date_str = match.group(1)
            return datetime.strptime(date_str, '%m/%d/%Y %H:%M:%S')
        except:
            pass
    return None

def format_calendar_note(event, use_extracted_subject=False):
    """Format calendar event into structured dispatch note."""
    lines = []
    
    # Subject line
    if use_extracted_subject and is_imap_failure(event.get('body', '')):
        extracted = extract_useful_subject_from_imap_failure(event['body'])
        if extracted:
            lines.append(f"📅 Calendar Event: {extracted}")
        else:
            lines.append(f"📅 Calendar Event: {event.get('subject', 'No subject')}")
    else:
        lines.append(f"📅 Calendar Event: {event.get('subject', 'No subject')}")
    
    # Location
    location = event.get('location', '').strip()
    if location:
        lines.append(f"📍 Location: {location}")
    
    # Time range
    start = event.get('start')
    end = event.get('end')
    if start and end:
        try:
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            lines.append(f"⏰ Time: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%H:%M')}")
        except:
            pass
    elif event.get('is_all_day'):
        lines.append(f"⏰ All-day event")
    
    # Body details (skip IMAP failures)
    body = event.get('body', '').strip()
    if body and not is_imap_failure(body):
        # Truncate long bodies
        if len(body) > 500:
            body = body[:500] + "..."
        lines.append(f"📝 Details: {body}")
    
    # Categories
    categories = event.get('categories', '').strip()
    if categories:
        lines.append(f"🏷️ Categories: {categories}")
    
    return "\n".join(lines)

def match_by_reserve_number(event, charters_dict):
    """Match event to charter by reserve_number."""
    reserve_numbers = event.get('reserve_numbers', [])
    matches = []
    for rn in reserve_numbers:
        if rn in charters_dict:
            matches.append(charters_dict[rn])
    return matches

def match_by_datetime(event, charters_by_date):
    """Match event to charter by date/time overlap - ONLY if has extracted_subject with details."""
    # Only match by datetime if we have extracted subject with actual content
    extracted_subject = event.get('extracted_subject', '')
    if not extracted_subject or len(extracted_subject) < 10:
        return []
    
    start = event.get('start')
    if not start:
        return []
    
    try:
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        date_key = start_dt.date().isoformat()
        
        if date_key in charters_by_date:
            # Only match if there's a single charter on that date
            charters = charters_by_date[date_key]
            if len(charters) == 1:
                return charters
    except:
        pass
    
    return []

def main():
    apply = '--apply' in sys.argv
    force_overwrite = '--force-overwrite' in sys.argv
    show_preview = '--show-preview' in sys.argv
    
    # Load calendar events
    calendar_path = os.path.join(os.path.dirname(__file__), '..', 'reports', 'calendar_0_events.json')
    if not os.path.exists(calendar_path):
        print(f"Error: Calendar events file not found: {calendar_path}")
        return
    
    with open(calendar_path, 'r', encoding='utf-8') as f:
        calendar_data = json.load(f)
    
    events = calendar_data.get('events', [])
    print(f"Loaded {len(events)} calendar events from {calendar_path}")
    
    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Load all charters with current booking_notes status
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, pickup_time, 
               booking_notes, client_notes
        FROM charters
        ORDER BY charter_date DESC
    """)
    charters = cur.fetchall()
    
    # Build lookup dictionaries
    charters_dict = {}  # reserve_number -> charter
    charters_by_date = {}  # date -> [charters]
    
    for charter in charters:
        charter_id, reserve_number, charter_date, pickup_time, booking_notes, client_notes = charter
        charter_obj = {
            'charter_id': charter_id,
            'reserve_number': reserve_number,
            'charter_date': charter_date,
            'pickup_time': pickup_time,
            'booking_notes': booking_notes,
            'client_notes': client_notes
        }
        
        if reserve_number:
            charters_dict[reserve_number] = charter_obj
        
        if charter_date:
            date_key = charter_date.isoformat()
            if date_key not in charters_by_date:
                charters_by_date[date_key] = []
            charters_by_date[date_key].append(charter_obj)
    
    print(f"Loaded {len(charters)} charters ({len(charters_dict)} with reserve_number)")
    
    # Process matches
    stats = {
        'total_events': len(events),
        'matched_by_reserve': 0,
        'matched_by_datetime': 0,
        'no_match': 0,
        'updates_planned': 0,
        'skipped_has_notes': 0,
        'skipped_imap_failure': 0
    }
    
    updates = []  # List of (charter_id, formatted_note)
    
    for event in events:
        # Extract data from IMAP failure if present
        body = event.get('body', '')
        extracted_subject = None
        
        if is_imap_failure(body):
            # Extract useful info from IMAP failure
            extracted_subject = extract_useful_subject_from_imap_failure(body)
            sent_date = extract_sent_date_from_imap_failure(body)
            
            # Update event with extracted info
            if extracted_subject:
                event['extracted_subject'] = extracted_subject
            
            if sent_date:
                event['extracted_date'] = sent_date
                # Use sent date for matching if no start date
                if not event.get('start'):
                    event['start'] = sent_date.isoformat()
        
        # Enhanced reserve number extraction from ALL fields
        reserve_pattern = r'\b(\d{6})\b'
        found_reserves = []
        
        # Search in all text fields
        search_fields = [
            event.get('subject', ''),
            event.get('extracted_subject', ''),
            event.get('location', ''),
            event.get('body', '') if not is_imap_failure(event.get('body', '')) else ''
        ]
        
        for field in search_fields:
            if field:
                field_reserves = re.findall(reserve_pattern, field)
                found_reserves.extend(field_reserves)
        
        # Remove duplicates and update event
        if found_reserves:
            event['reserve_numbers'] = list(set(found_reserves))
        
        # Try reserve number match first
        matches = match_by_reserve_number(event, charters_dict)
        if matches:
            stats['matched_by_reserve'] += len(matches)
        else:
            # Try datetime match
            matches = match_by_datetime(event, charters_by_date)
            if matches:
                stats['matched_by_datetime'] += len(matches)
            else:
                stats['no_match'] += 1
                continue
        
        # Format note
        note = format_calendar_note(event, use_extracted_subject=True)
        
        # Process matches
        for charter in matches:
            # Check if notes already exist
            if charter['booking_notes'] and charter['booking_notes'].strip():
                if not force_overwrite:
                    stats['skipped_has_notes'] += 1
                    continue
            
            # Plan update
            updates.append((charter['charter_id'], charter['reserve_number'], note))
            stats['updates_planned'] += 1
    
    # Preview mode
    if show_preview and updates:
        print("\n" + "="*80)
        print("PREVIEW OF UPDATES (first 5):")
        print("="*80)
        for charter_id, reserve_number, note in updates[:5]:
            print(f"\nCharter {charter_id} (Reserve: {reserve_number}):")
            print("-" * 80)
            print(note)
            print("-" * 80)
    
    # Apply updates
    if apply and updates:
        print(f"\nApplying {len(updates)} updates...")
        for charter_id, reserve_number, note in updates:
            cur.execute("""
                UPDATE charters 
                SET booking_notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE charter_id = %s
            """, (note, charter_id))
        
        conn.commit()
        print(f"[OK] Successfully updated {len(updates)} charters")
    elif not apply:
        print(f"\n🔍 DRY RUN: Would update {len(updates)} charters")
        print("   Add --apply to execute updates")
    
    # Print statistics
    print("\n" + "="*80)
    print("MATCHING STATISTICS:")
    print("="*80)
    print(f"Total events processed:        {stats['total_events']:,}")
    print(f"Matched by reserve number:     {stats['matched_by_reserve']:,}")
    print(f"Matched by date/time:          {stats['matched_by_datetime']:,}")
    print(f"No match found:                {stats['no_match']:,}")
    print(f"Skipped (IMAP failure):        {stats['skipped_imap_failure']:,}")
    print(f"Skipped (has existing notes):  {stats['skipped_has_notes']:,}")
    print(f"Updates {'applied' if apply else 'planned'}:              {stats['updates_planned']:,}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
