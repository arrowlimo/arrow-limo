#!/usr/bin/env python3
"""
Create Outlook calendar appointments for charters missing from calendar.
Reads charters with calendar_sync_status = 'not_in_calendar' and creates
appointments in the 'arrow new' Outlook calendar.
"""

import win32com.client
import pythoncom
import psycopg2
import sys
import os
from datetime import datetime, timedelta
import argparse

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def find_calendar_folder(outlook, folder_name):
    """Recursively find a calendar folder by name."""
    namespace = outlook.GetNamespace("MAPI")
    
    def search_folders(folder):
        """Recursively search folders."""
        if folder.Name.lower() == folder_name.lower():
            if folder.DefaultItemType == 1:  # olAppointmentItem = 1
                return folder
        
        try:
            for subfolder in folder.Folders:
                result = search_folders(subfolder)
                if result:
                    return result
        except:
            pass
        
        return None
    
    # Start from default calendar
    default_cal = namespace.GetDefaultFolder(9)  # olFolderCalendar
    result = search_folders(default_cal.Parent)
    
    if not result:
        result = search_folders(default_cal)
    
    return result


def build_appointment_subject(charter):
    """Build appointment subject line: Vehicle - Client Name."""
    vehicle = charter.get('vehicle_number') or ''
    client = charter.get('client_display_name') or charter.get('client_name') or 'Unknown Client'
    
    # Format: "L-3 - One Call Medical Transports"
    if vehicle:
        return f"{vehicle} - {client}"
    else:
        return client


def build_appointment_location(charter):
    """Build appointment location field: Reserve# Driver.
    Prefers active drivers, shows status if inactive.
    """
    reserve = charter['reserve_number']
    driver = charter.get('driver_full_name') or charter.get('driver_name') or ''
    driver_status = charter.get('driver_status', '')
    
    # Format: "019708 Mark" or "019708 Mark (inactive)" or just "019708"
    if driver:
        # Extract first name only
        first_name = driver.split()[0] if ' ' in driver else driver
        
        # Add status indicator if inactive
        if driver_status and driver_status.lower() != 'active':
            return f"{reserve} {first_name} ({driver_status})"
        else:
            return f"{reserve} {first_name}"
    else:
        return reserve


def parse_outlook_subject(subject):
    """Parse Outlook subject to extract vehicle and client.
    Format: 'L-3 - One Call Medical Transports' or just 'Client Name'
    Returns: (vehicle, client)
    """
    if not subject:
        return None, None
    
    parts = subject.split(' - ', 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    else:
        return None, parts[0].strip()


def parse_outlook_location(location):
    """Parse Outlook location to extract reserve number and driver.
    Format: '019708 Mark' or just '019708'
    Returns: (reserve_number, driver_first_name)
    """
    if not location:
        return None, None
    
    parts = location.split(None, 1)  # Split on first whitespace
    reserve = parts[0].strip()
    driver = parts[1].strip() if len(parts) > 1 else None
    
    return reserve, driver


def needs_midnight_split(charter_date, start_time, end_time):
    """Check if appointment crosses midnight and needs split."""
    if not end_time or not start_time:
        return False
    
    # If end time is earlier than start time, it crosses midnight
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%H:%M:%S").time()
    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, "%H:%M:%S").time()
    
    return end_time < start_time


def build_appointment_body(charter):
    """Build structured appointment body text with title/location for data integrity."""
    lines = []
    
    # Add title and location at top for data integrity backup
    subject = build_appointment_subject(charter)
    location = build_appointment_location(charter)
    lines.append(f"TITLE: {subject}")
    lines.append(f"LOCATION: {location}")
    lines.append("")  # Blank line
    
    lines.append(f"Reserve: {charter['reserve_number']}")
    
    client = charter.get('client_display_name') or charter.get('client_name')
    if client:
        lines.append(f"Client: {client}")
    
    driver = charter.get('driver_full_name')
    if driver:
        lines.append(f"Driver: {driver}")
    
    vehicle = charter.get('vehicle_number')
    if vehicle:
        lines.append(f"Vehicle: {vehicle}")
    
    if charter.get('pickup_address'):
        lines.append(f"Pickup: {charter['pickup_address']}")
    
    if charter.get('dropoff_address'):
        lines.append(f"Dropoff: {charter['dropoff_address']}")
    
    if charter.get('passenger_count'):
        lines.append(f"Passengers: {charter['passenger_count']}")
    
    if charter.get('total_amount_due'):
        amount = charter['total_amount_due']
        paid = charter.get('paid_amount') or 0
        balance = amount - paid
        lines.append(f"Amount: ${amount:.2f}")
        lines.append(f"Paid: ${paid:.2f}")
        
        if balance > 0:
            lines.append(f"Balance Due: ${balance:.2f}")
        else:
            lines.append("Status: PAID IN FULL")
    
    if charter.get('charter_notes'):
        lines.append(f"\nNotes:\n{charter['charter_notes']}")
    
    return "\n".join(lines)


def create_outlook_appointment(outlook, calendar_folder, charter, is_split_part2=False):
    """Create new Outlook appointment from charter data.
    
    Args:
        is_split_part2: If True, this is day 2 of midnight-crossing appointment
    """
    appt = outlook.CreateItem(1)  # 1 = olAppointmentItem
    
    # Set basic fields
    subject = build_appointment_subject(charter)
    if is_split_part2:
        subject += " (cont.)"  # Mark continuation
    appt.Subject = subject
    appt.Location = build_appointment_location(charter)
    appt.Body = build_appointment_body(charter)
    
    # Set date/time
    charter_date = charter['charter_date']
    pickup_time = charter.get('pickup_time')
    dropoff_time = charter.get('dropoff_time')
    
    # Handle midnight split
    if is_split_part2:
        # Part 2: Midnight to dropoff_time on next day
        start_dt = datetime.combine(charter_date + timedelta(days=1), datetime.min.time())
        if dropoff_time:
            if isinstance(dropoff_time, str):
                dropoff_time = datetime.strptime(dropoff_time, "%H:%M:%S").time()
            end_dt = datetime.combine(charter_date + timedelta(days=1), dropoff_time)
        else:
            end_dt = start_dt + timedelta(hours=2)
    else:
        # Normal or Part 1 of split
        if pickup_time:
            if isinstance(pickup_time, str):
                pickup_time = datetime.strptime(pickup_time, "%H:%M:%S").time()
            start_dt = datetime.combine(charter_date, pickup_time)
        else:
            start_dt = datetime.combine(charter_date, datetime.min.time())
            appt.AllDayEvent = True
        
        if dropoff_time:
            if isinstance(dropoff_time, str):
                dropoff_time = datetime.strptime(dropoff_time, "%H:%M:%S").time()
            
            # Check if crosses midnight
            if needs_midnight_split(charter_date, pickup_time, dropoff_time):
                # Part 1: pickup_time to 11:59 PM same day
                end_dt = datetime.combine(charter_date, datetime.max.time().replace(microsecond=0))
            else:
                end_dt = datetime.combine(charter_date, dropoff_time)
        else:
            # Default 2 hour duration
            end_dt = start_dt + timedelta(hours=2)
    
    appt.Start = start_dt
    appt.End = end_dt
    
    # Move to target calendar
    if calendar_folder:
        appt.Move(calendar_folder)
    
    # Save appointment
    appt.Save()
    
    return appt.EntryID


def sync_charters_to_outlook(year=2026, dry_run=True, reserve_number=None):
    """Create Outlook appointments for charters not in calendar."""
    
    print(f"=" * 70)
    if reserve_number:
        print(f"CREATE OUTLOOK APPOINTMENT FOR RESERVE {reserve_number}")
    else:
        print(f"CREATE MISSING OUTLOOK APPOINTMENTS - {year}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'WRITE (creating appointments)'}")
    print(f"=" * 70)
    
    # Connect to database
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Build query based on whether specific reserve requested
    if reserve_number:
        query = """
            SELECT c.charter_id, c.reserve_number, c.charter_date,
                   c.pickup_time, c.dropoff_time,
                   c.client_display_name, c.pickup_address, c.dropoff_address,
                   c.total_amount_due, c.paid_amount,
                   c.passenger_count, c.charter_notes,
                   v.vehicle_number, e.full_name as driver_full_name, e.status as driver_status
            FROM charters c
            LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
            LEFT JOIN employees e ON c.employee_id = e.employee_id
            WHERE c.reserve_number = %s
              AND (c.status IS NULL OR c.status != 'cancelled')
        """
        params = (reserve_number,)
    else:
        query = """
            SELECT c.charter_id, c.reserve_number, c.charter_date,
                   c.pickup_time, c.dropoff_time,
                   c.client_display_name, c.pickup_address, c.dropoff_address,
                   c.total_amount_due, c.paid_amount,
                   c.passenger_count, c.charter_notes,
                   v.vehicle_number, e.full_name as driver_full_name, e.status as driver_status
            FROM charters c
            LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
            LEFT JOIN employees e ON c.employee_id = e.employee_id
            WHERE EXTRACT(YEAR FROM c.charter_date) = %s
              AND (c.calendar_sync_status = 'not_in_calendar' OR c.calendar_sync_status IS NULL)
              AND (c.status IS NULL OR c.status != 'cancelled')
            ORDER BY c.charter_date, c.pickup_time
        """
        params = (year,)
    
    cur.execute(query, params)
    
    columns = [desc[0] for desc in cur.description]
    charters = [dict(zip(columns, row)) for row in cur.fetchall()]
    
    if reserve_number:
        print(f"\nFound charter: {reserve_number}\n")
        if len(charters) == 0:
            print(f"❌ Reserve {reserve_number} not found or already cancelled")
            cur.close()
            conn.close()
            return
    else:
        print(f"\nFound {len(charters)} charters missing from Outlook calendar\n")
        
        if len(charters) == 0:
            print("✅ All charters are already in calendar!")
            cur.close()
            conn.close()
            return
    
    if dry_run:
        print("DRY RUN - Would create these appointments:\n")
        for charter in charters[:10]:  # Show first 10
            client = charter.get('client_display_name') or 'Unknown'
            vehicle = charter.get('vehicle_number') or ''
            reserve = charter['reserve_number']
            
            # Check midnight split
            pickup = charter.get('pickup_time')
            dropoff = charter.get('dropoff_time')
            split = " [SPLITS AT MIDNIGHT]" if needs_midnight_split(charter['charter_date'], pickup, dropoff) else ""
            
            print(f"  {charter['charter_date']} - {vehicle} - {client} - #{reserve}{split}")
        
        if len(charters) > 10:
            print(f"  ... and {len(charters) - 10} more")
        
        print(f"\nRun with --write to create {len(charters)} appointments")
        cur.close()
        conn.close()
        return
    
    # Initialize Outlook COM
    pythoncom.CoInitialize()
    
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        print("✓ Connected to Outlook")
        
        # Find target calendar
        calendar_folder = find_calendar_folder(outlook, 'arrow new')
        
        if not calendar_folder:
            print("ERROR: Could not find 'arrow new' calendar folder")
            print("Available calendars:")
            namespace = outlook.GetNamespace("MAPI")
            default_cal = namespace.GetDefaultFolder(9)
            print(f"  - {default_cal.Name} (default)")
            
            cur.close()
            conn.close()
            return
        
        print(f"✓ Found calendar: {calendar_folder.Name}")
        print(f"\nCreating {len(charters)} appointments...\n")
        
        created_count = 0
        error_count = 0
        
        for idx, charter in enumerate(charters, 1):
            try:
                if idx % 10 == 0:
                    print(f"  Progress: {idx}/{len(charters)}...")
                
                # Create appointment (part 1)
                entry_id = create_outlook_appointment(outlook, calendar_folder, charter, is_split_part2=False)
                
                # Check if needs midnight split (create part 2)
                pickup_time = charter.get('pickup_time')
                dropoff_time = charter.get('dropoff_time')
                if needs_midnight_split(charter['charter_date'], pickup_time, dropoff_time):
                    print(f"    ⚠ {charter['reserve_number']} crosses midnight - creating 2 appointments")
                    create_outlook_appointment(outlook, calendar_folder, charter, is_split_part2=True)
                
                # Update charter with sync status
                cur.execute("""
                    UPDATE charters
                    SET calendar_sync_status = 'synced',
                        calendar_color = 'blue',
                        outlook_entry_id = %s,
                        calendar_notes = 'Created via sync on ' || CURRENT_TIMESTAMP::text
                    WHERE charter_id = %s
                """, (entry_id, charter['charter_id']))
                
                created_count += 1
                
            except Exception as e:
                print(f"  ✗ Error creating {charter['reserve_number']}: {e}")
                error_count += 1
        
        conn.commit()
        
        print(f"\n" + "=" * 70)
        print(f"SUMMARY:")
        print(f"  ✓ Created: {created_count} appointments")
        if error_count > 0:
            print(f"  ✗ Errors: {error_count}")
        print(f"=" * 70)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    
    finally:
        pythoncom.CoUninitialize()
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description='Create missing Outlook appointments from charters')
    parser.add_argument('--year', type=int, default=2026,
                        help='Year to process (default: 2026)')
    parser.add_argument('--reserve', type=str,
                        help='Sync a specific reserve number only')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview what would be created without making changes')
    parser.add_argument('--write', action='store_true',
                        help='Actually create appointments in Outlook')
    
    args = parser.parse_args()
    
    if not args.write:
        args.dry_run = True
    
    sync_charters_to_outlook(year=args.year, dry_run=args.dry_run, reserve_number=args.reserve)


if __name__ == '__main__':
    main()
