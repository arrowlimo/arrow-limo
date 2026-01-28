#!/usr/bin/env python3
"""
Find charters that are NOT in the Arrow calendar CSV
This identifies charters that weren't tracked in the calendar system
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import csv
import re

CALENDAR_FILE = r'l:\limo\qb_storage\exports_verified\arrow limousine calender.CSV'

def parse_reserve_number(text):
    """Extract 6-digit reserve number from text"""
    if not text:
        return None
    # Look for 6-digit numbers (reserve numbers)
    match = re.search(r'\b(\d{6})\b', str(text))
    if match:
        return match.group(1)
    return None

def load_calendar_reserves():
    """Load all reserve numbers from calendar CSV"""
    
    print("📅 Loading calendar data...")
    
    calendar_reserves = set()
    
    with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # Check Subject and Location fields for reserve numbers
            for field in ['Subject', 'Location', 'Description']:
                if field in row:
                    reserve = parse_reserve_number(row[field])
                    if reserve:
                        calendar_reserves.add(reserve)
    
    print(f"   ✓ Found {len(calendar_reserves):,} unique reserve numbers in calendar")
    
    return calendar_reserves

def find_missing_charters(calendar_reserves):
    """Find charters NOT in calendar"""
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 70)
    print("CHARTERS NOT IN CALENDAR")
    print("=" * 70)
    
    # Get all active charters
    cur.execute("""
        SELECT COUNT(*) as total
        FROM charters
        WHERE cancelled = false
        AND reserve_number ~ '^[0-9]{6}$'
    """)
    
    total = cur.fetchone()['total']
    
    # Get charters not in calendar
    placeholders = ','.join(['%s'] * len(calendar_reserves))
    
    cur.execute(f"""
        SELECT reserve_number, charter_date, 
               client_id, rate, balance, total_amount_due,
               assigned_driver_id,
               CASE WHEN EXISTS (
                   SELECT 1 FROM driver_payroll dp 
                   WHERE dp.charter_id::integer = c.charter_id
                   AND (dp.payroll_class = 'WAGE' OR dp.payroll_class IS NULL)
               ) THEN true ELSE false END as has_payroll
        FROM charters c
        WHERE c.cancelled = false
        AND c.reserve_number ~ '^[0-9]{{6}}$'
        AND c.reserve_number NOT IN ({placeholders})
        ORDER BY c.charter_date DESC NULLS LAST
    """, list(calendar_reserves))
    
    missing = cur.fetchall()
    missing_count = len(missing)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total active charters (6-digit): {total:,}")
    print(f"   In calendar: {len(calendar_reserves):,}")
    print(f"   NOT in calendar: {missing_count:,} ({missing_count/total*100:.1f}%)")
    
    # Analyze missing charters by date range
    print(f"\n📅 MISSING CHARTERS BY DATE RANGE:")
    
    # Null dates
    null_date = sum(1 for m in missing if m['charter_date'] is None)
    if null_date > 0:
        print(f"   NULL date: {null_date:,}")
    
    # By year
    from collections import defaultdict
    by_year = defaultdict(int)
    for m in missing:
        if m['charter_date']:
            year = m['charter_date'].year
            by_year[year] += 1
    
    for year in sorted(by_year.keys()):
        print(f"   {year}: {by_year[year]:,}")
    
    # Analyze characteristics
    with_driver = sum(1 for m in missing if m['assigned_driver_id'])
    with_payroll = sum(1 for m in missing if m['has_payroll'])
    with_balance = sum(1 for m in missing if m['balance'] and m['balance'] != 0)
    
    print(f"\n🔍 CHARACTERISTICS OF MISSING CHARTERS:")
    print(f"   With driver assigned: {with_driver:,} ({with_driver/missing_count*100:.1f}%)")
    print(f"   With payroll: {with_payroll:,} ({with_payroll/missing_count*100:.1f}%)")
    print(f"   With balance owing: {with_balance:,}")
    
    # Sample recent missing
    print(f"\n📋 SAMPLE RECENT MISSING CHARTERS (last 20):")
    for i, row in enumerate(missing[:20]):
        date_str = str(row['charter_date']) if row['charter_date'] else 'No date'
        driver = '✓ Driver' if row['assigned_driver_id'] else '✗ No driver'
        payroll = '✓ Payroll' if row['has_payroll'] else '✗ No payroll'
        balance_str = f"${row['balance']:.2f}" if row['balance'] else "$0.00"
        print(f"   {row['reserve_number']} ({date_str}): {driver}, {payroll}, Bal: {balance_str}")
    
    # Sample oldest missing
    if len(missing) > 20:
        print(f"\n📋 SAMPLE OLDEST MISSING CHARTERS (first 10):")
        for row in missing[-10:]:
            date_str = str(row['charter_date']) if row['charter_date'] else 'No date'
            driver = '✓ Driver' if row['assigned_driver_id'] else '✗ No driver'
            payroll = '✓ Payroll' if row['has_payroll'] else '✗ No payroll'
            print(f"   {row['reserve_number']} ({date_str}): {driver}, {payroll}")
    
    conn.close()
    
    return missing

def main():
    print("=" * 70)
    print("CHARTERS NOT IN ARROW CALENDAR")
    print("=" * 70)
    print("\nIdentifying charters that weren't tracked in the calendar system.")
    print("=" * 70)
    
    # Load calendar reserves
    calendar_reserves = load_calendar_reserves()
    
    # Find missing charters
    missing = find_missing_charters(calendar_reserves)
    
    print("\n" + "=" * 70)
    print("✓ Analysis complete")
    print("=" * 70)

if __name__ == '__main__':
    main()
