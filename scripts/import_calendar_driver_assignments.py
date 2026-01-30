#!/usr/bin/env python3
"""
Import driver assignments from Arrow Limousine Outlook calendar export

The calendar Location field often contains driver names, and may have TWO names
if one driver was scheduled but replaced by another (e.g., "019474 alana" or 
"019469 allana   recheck time to leave").

Strategy:
- Parse calendar entries for reserve numbers
- Extract driver names from Location field (loose matching)
- Handle multiple names (scheduled vs actual driver)
- Link driver names to employee records via fuzzy matching
- Update charters.assigned_driver_id with actual driver worked
"""

import csv
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from collections import defaultdict
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def parse_reserve_number(text):
    """Extract 6-digit reserve number from text"""
    if not text:
        return None
    match = re.search(r'\b(0\d{5})\b', text)
    return match.group(1) if match else None

def extract_driver_names(location_text, description_text=""):
    """
    Extract potential driver names from location/description fields.
    Handles multiple names (scheduled vs replaced driver).
    Returns list of potential driver names (lowercase, cleaned).
    
    Focus on location field ONLY - descriptions are too noisy.
    """
    if not location_text:
        return []
    
    # Remove reserve numbers first
    text_clean = re.sub(r'\b0\d{5}\b', '', location_text)
    
    # Remove common non-name words
    stopwords = ['recheck', 'time', 'leave', 'says', 'mins', 'location', 'calgary', 
                 'from', 'return', 'trip', 'cancelled', 'flight', 'yyc', 'airport',
                 'home', 'receipt', 'westjet', 'pick', 'arrives', 'departs', 'take',
                 'gursky', 'mundy', 'hotel', 'street', 'paid', 'full', 'total']
    
    for stopword in stopwords:
        text_clean = re.sub(r'\b' + stopword + r'\b', '', text_clean, flags=re.IGNORECASE)
    
    # Extract potential names (words that are 3-12 letters, alphabetic)
    potential_names = []
    words = text_clean.split()
    
    for word in words:
        word_clean = re.sub(r'[^\w]', '', word).strip()
        # Must be 3-12 letters (names are rarely longer), all alphabetic
        if 3 <= len(word_clean) <= 12 and word_clean.isalpha():
            potential_names.append(word_clean.lower())
    
    return potential_names

def build_driver_name_map(conn):
    """
    Build mapping of driver name variations to employee_id
    Uses first_name, last_name, full_name from employees table
    Includes common nickname mappings
    """
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT employee_id, first_name, last_name, full_name, 
               driver_code, employee_number
        FROM employees
        WHERE is_chauffeur = true
        ORDER BY employee_id
    """)
    
    employees = cur.fetchall()
    
    # Common nickname/short name mappings
    nickname_map = {
        'dave': ['david', 'davey'],
        'vic': ['victor', 'vince', 'vincent'],
        'jay': ['jason', 'james', 'jayson'],
        'ron': ['ronald', 'ronnie'],
        'sam': ['samuel', 'samantha'],
        'mike': ['michael', 'mick', 'mickey'],
        'matt': ['matthew', 'matthias'],
        'rob': ['robert', 'robbie', 'bobby'],
        'dan': ['daniel', 'danny'],
        'joe': ['joseph', 'joey'],
        'chris': ['christopher', 'christian', 'christine', 'christina'],
        'tom': ['thomas', 'tommy'],
        'jim': ['james', 'jimmy'],
        'bill': ['william', 'billy'],
        'tony': ['anthony', 'antonio'],
        'rick': ['richard', 'ricky', 'dick'],
        'steve': ['steven', 'stephen'],
        'greg': ['gregory', 'gregg'],
        'ken': ['kenneth', 'kenny'],
        'tim': ['timothy', 'timmy'],
        'brit': ['brittany', 'britta', 'brittney'],
        'tabitha': ['tabatha'],
        'allana': ['alana', 'alanna'],
    }
    
    # Build name -> employee_id mapping (with variations)
    name_map = {}
    
    for emp in employees:
        emp_id = emp['employee_id']
        
        # Collect all name parts from all fields
        all_name_parts = []
        
        # Add first name parts (may contain middle names)
        if emp['first_name']:
            first_parts = emp['first_name'].lower().strip().split()
            all_name_parts.extend(first_parts)
        
        # Add last name parts
        if emp['last_name']:
            last_parts = emp['last_name'].lower().strip().split()
            all_name_parts.extend(last_parts)
        
        # Add full name parts (captures everything)
        if emp['full_name']:
            full_parts = emp['full_name'].lower().split()
            all_name_parts.extend(full_parts)
        
        # Remove duplicates and filter out commas/punctuation
        clean_parts = set()
        for part in all_name_parts:
            part_clean = re.sub(r'[^\w]', '', part).strip()
            if len(part_clean) >= 2:
                clean_parts.add(part_clean)
        
        # Map each name part to this employee
        for part in clean_parts:
            if part not in name_map:
                name_map[part] = []
            if emp_id not in name_map[part]:
                name_map[part].append(emp_id)
            
            # Add nickname variations if this name maps to nicknames
            for nickname, full_names in nickname_map.items():
                if part in full_names:
                    if nickname not in name_map:
                        name_map[nickname] = []
                    if emp_id not in name_map[nickname]:
                        name_map[nickname].append(emp_id)
    
    cur.close()
    return name_map, {emp['employee_id']: emp for emp in employees}

def match_driver_names_to_employees(driver_names, name_map):
    """
    Match list of potential driver names to employee IDs.
    Returns list of (employee_id, confidence) tuples.
    
    If multiple names found, later names in list are preferred
    (as they likely represent the actual/replacement driver)
    """
    matches = []
    
    for idx, name in enumerate(driver_names):
        if name in name_map:
            employee_ids = name_map[name]
            # Higher confidence for later names (replacement drivers)
            confidence = 0.7 + (idx * 0.1)  # First name 0.7, second 0.8, etc.
            
            for emp_id in employee_ids:
                matches.append((emp_id, confidence, name))
    
    # Sort by confidence descending (prefer later/replacement drivers)
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches

def parse_calendar_file(calendar_path):
    """Parse Outlook calendar CSV and extract driver assignment data"""
    
    print(f"📅 Parsing calendar file: {calendar_path}")
    
    assignments = []
    
    with open(calendar_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        
        for row_num, row in enumerate(reader, start=2):
            if len(row) < 17:
                continue
            
            subject = row[0].strip('"')
            start_date = row[1]
            start_time = row[2]
            description = row[15] if len(row) > 15 else ""
            location = row[16] if len(row) > 16 else ""
            
            # Extract reserve number from location or description
            reserve = parse_reserve_number(location)
            if not reserve:
                reserve = parse_reserve_number(description)
            if not reserve:
                reserve = parse_reserve_number(subject)
            
            if not reserve:
                continue
            
            # Extract vehicle assignment from subject (L4, L20, etc.)
            vehicle_match = re.search(r'\bL(\d+)\b', subject)
            vehicle_code = f"L{vehicle_match.group(1)}" if vehicle_match else None
            
            # Extract driver names
            driver_names = extract_driver_names(location, description)
            
            if driver_names or vehicle_code:
                assignments.append({
                    'reserve_number': reserve,
                    'calendar_date': start_date,
                    'calendar_time': start_time,
                    'vehicle_code': vehicle_code,
                    'driver_names': driver_names,
                    'location_text': location[:200],
                    'subject': subject[:200],
                    'row_number': row_num
                })
    
    print(f"   Found {len(assignments)} calendar entries with reserve numbers")
    return assignments

def analyze_calendar_assignments(assignments, name_map, employee_details):
    """Analyze calendar assignments and match to employees"""
    
    print(f"\n🔍 Analyzing driver name matches...")
    
    matched_assignments = []
    unmatched_names = defaultdict(int)
    
    for assign in assignments:
        driver_matches = match_driver_names_to_employees(assign['driver_names'], name_map)
        
        if driver_matches:
            # Take highest confidence match
            best_match = driver_matches[0]
            emp_id, confidence, matched_name = best_match
            
            emp = employee_details[emp_id]
            
            matched_assignments.append({
                **assign,
                'employee_id': emp_id,
                'employee_name': emp['full_name'],
                'confidence': confidence,
                'matched_name': matched_name,
                'all_matches': driver_matches
            })
        else:
            # Track unmatched names for manual review
            for name in assign['driver_names']:
                unmatched_names[name] += 1
    
    print(f"   Matched: {len(matched_assignments)} assignments")
    print(f"   Unmatched driver names: {len(unmatched_names)} unique names")
    
    if unmatched_names:
        print(f"\n   Top 20 unmatched names:")
        for name, count in sorted(unmatched_names.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"      {name}: {count} times")
    
    return matched_assignments, unmatched_names

def link_to_charters(conn, matched_assignments, dry_run=True):
    """Link calendar driver assignments to charters table"""
    
    print(f"\n🔗 Linking calendar assignments to charters...")
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get existing charters
    cur.execute("""
        SELECT charter_id, reserve_number, assigned_driver_id, charter_date
        FROM charters
        WHERE reserve_number IS NOT NULL
    """)
    
    charters = {c['reserve_number']: c for c in cur.fetchall()}
    
    updates_needed = []
    already_assigned = []
    not_found = []
    
    for assign in matched_assignments:
        reserve = assign['reserve_number']
        
        if reserve not in charters:
            not_found.append(assign)
            continue
        
        charter = charters[reserve]
        
        if charter['assigned_driver_id']:
            already_assigned.append({
                'reserve': reserve,
                'existing': charter['assigned_driver_id'],
                'calendar': assign['employee_id'],
                'calendar_name': assign['employee_name']
            })
        else:
            updates_needed.append({
                'charter_id': charter['charter_id'],
                'reserve_number': reserve,
                'employee_id': assign['employee_id'],
                'employee_name': assign['employee_name'],
                'confidence': assign['confidence'],
                'driver_names': assign['driver_names'],
                'vehicle_code': assign['vehicle_code']
            })
    
    print(f"\n📊 CALENDAR LINKAGE RESULTS:")
    print(f"   Total calendar assignments: {len(matched_assignments)}")
    print(f"   Charters needing driver assignment: {len(updates_needed)}")
    print(f"   Charters already assigned: {len(already_assigned)}")
    print(f"   Reserve numbers not found: {len(not_found)}")
    
    if updates_needed:
        print(f"\n   Sample updates needed:")
        for update in updates_needed[:10]:
            print(f"      Charter {update['reserve_number']}: → {update['employee_name']} "
                  f"(confidence: {update['confidence']:.2f}, names: {update['driver_names']})")
    
    if already_assigned:
        print(f"\n   Sample already assigned:")
        for item in already_assigned[:10]:
            print(f"      Charter {item['reserve']}: existing={item['existing']}, "
                  f"calendar={item['calendar']} ({item['calendar_name']})")
    
    if not dry_run:
        print(f"\n✍️  APPLYING UPDATES...")
        update_count = 0
        
        for update in updates_needed:
            cur.execute("""
                UPDATE charters
                SET assigned_driver_id = %s,
                    driver_notes = COALESCE(driver_notes || E'\n', '') || 
                                  'Driver assigned from calendar: ' || %s || 
                                  ' (confidence: ' || %s || ', names: ' || %s || ')'
                WHERE charter_id = %s
            """, (
                update['employee_id'],
                update['employee_name'],
                f"{update['confidence']:.2f}",
                ', '.join(update['driver_names']),
                update['charter_id']
            ))
            update_count += 1
        
        conn.commit()
        print(f"   [OK] Updated {update_count} charters with driver assignments")
    else:
        print(f"\n   🔍 DRY RUN - Use --write to apply updates")
    
    cur.close()
    return updates_needed, already_assigned, not_found

def main():
    parser = argparse.ArgumentParser(
        description='Import driver assignments from Arrow Limousine calendar'
    )
    parser.add_argument('--calendar', 
                       default=r'l:\limo\qb_storage\exports_verified\arrow limousine calender.CSV',
                       help='Path to calendar CSV file')
    parser.add_argument('--write', action='store_true',
                       help='Apply updates (default is dry-run)')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                       help='Minimum confidence for driver matching (0.0-1.0)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("IMPORT DRIVER ASSIGNMENTS FROM ARROW LIMOUSINE CALENDAR")
    print("=" * 80)
    
    # Parse calendar file
    assignments = parse_calendar_file(args.calendar)
    
    # Connect to database
    conn = get_db_connection()
    
    try:
        # Build driver name mapping
        print(f"\n👥 Building driver name mapping from employees table...")
        name_map, employee_details = build_driver_name_map(conn)
        print(f"   Mapped {len(name_map)} name variations to {len(employee_details)} chauffeurs")
        
        # Analyze and match driver names
        matched_assignments, unmatched_names = analyze_calendar_assignments(
            assignments, name_map, employee_details
        )
        
        # Filter by confidence threshold
        filtered_assignments = [a for a in matched_assignments if a['confidence'] >= args.min_confidence]
        print(f"\n   After confidence filter (>={args.min_confidence}): {len(filtered_assignments)} assignments")
        
        # Link to charters and update
        updates, already_assigned, not_found = link_to_charters(
            conn, filtered_assignments, dry_run=not args.write
        )
        
        print(f"\n" + "=" * 80)
        print("SUMMARY:")
        print("=" * 80)
        print(f"""
Calendar Processing:
- Calendar entries parsed: {len(assignments)}
- Driver names matched: {len(matched_assignments)}
- Confidence threshold: {args.min_confidence}
- Qualifying assignments: {len(filtered_assignments)}

Charter Updates:
- New assignments to apply: {len(updates)}
- Already assigned: {len(already_assigned)}
- Reserve numbers not found: {len(not_found)}

{'[OK] UPDATES APPLIED' if args.write else '🔍 DRY RUN MODE - Use --write to apply'}
        """)
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
