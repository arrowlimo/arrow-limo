"""
Investigate root cause of charter date import error.
Analyzes how 39 charters got assigned 2025-08-06 instead of correct dates.
"""
import psycopg2
import pyodbc
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def get_lms_connection():
    """Connect to LMS Access database."""
    lms_path = r'L:\limo\backups\lms.mdb'
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    return pyodbc.connect(conn_str)

def main():
    pg_conn = get_db_connection()
    lms_conn = get_lms_connection()
    
    pg_cur = pg_conn.cursor()
    lms_cur = lms_conn.cursor()
    
    print("="*80)
    print("CHARTER DATE IMPORT ERROR INVESTIGATION")
    print("="*80)
    print()
    
    # Get the 39 corrected charters from backup table
    print("Analyzing corrected charters from backup table...")
    pg_cur.execute("""
        SELECT reserve_number, charter_date, total_amount_due, created_at, updated_at
        FROM charters_date_backup_20251123_172104
        ORDER BY reserve_number
    """)
    backup_records = pg_cur.fetchall()
    
    print(f"Found {len(backup_records)} records in backup (all showed 2025-08-06)")
    print()
    
    # Check created_at and updated_at timestamps
    print("TIMESTAMP ANALYSIS:")
    print("-" * 80)
    print(f"{'Reserve':<10} {'Created At':<20} {'Updated At':<20} {'Date Assigned':<12}")
    print("-" * 80)
    
    created_dates = {}
    updated_dates = {}
    
    for reserve, charter_date, total, created_at, updated_at in backup_records[:10]:  # Show first 10
        created_str = created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else 'NULL'
        updated_str = updated_at.strftime('%Y-%m-%d %H:%M:%S') if updated_at else 'NULL'
        date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'NULL'
        
        print(f"{reserve:<10} {created_str:<20} {updated_str:<20} {date_str:<12}")
        
        if created_at:
            created_date = created_at.date()
            created_dates[created_date] = created_dates.get(created_date, 0) + 1
        
        if updated_at:
            updated_date = updated_at.date()
            updated_dates[updated_date] = updated_dates.get(updated_date, 0) + 1
    
    print(f"... ({len(backup_records) - 10} more records)")
    print()
    
    # Summarize timestamp patterns
    print("TIMESTAMP PATTERN SUMMARY:")
    print("-" * 80)
    if created_dates:
        print("Created dates distribution:")
        for date, count in sorted(created_dates.items(), key=lambda x: x[1], reverse=True):
            print(f"  {date}: {count} charters")
    print()
    
    if updated_dates:
        print("Updated dates distribution:")
        for date, count in sorted(updated_dates.items(), key=lambda x: x[1], reverse=True):
            print(f"  {date}: {count} charters")
    print()
    
    # Check for common import patterns
    print("CHECKING FOR IMPORT PATTERNS:")
    print("-" * 80)
    
    # Check if all 39 have similar creation timestamps
    pg_cur.execute("""
        SELECT 
            DATE(created_at) as creation_date,
            COUNT(*) as charter_count,
            MIN(created_at) as first_created,
            MAX(created_at) as last_created
        FROM charters_date_backup_20251123_172104
        WHERE created_at IS NOT NULL
        GROUP BY DATE(created_at)
        ORDER BY creation_date DESC
    """)
    
    print("Creation date clusters:")
    for creation_date, count, first, last in pg_cur.fetchall():
        time_span = (last - first).total_seconds() / 60  # minutes
        print(f"  {creation_date}: {count} charters (span: {time_span:.1f} minutes)")
    print()
    
    # Check LMS for when these reserves were actually created
    print("CHECKING LMS CREATION DATES:")
    print("-" * 80)
    
    reserve_numbers = [str(r[0]) for r in backup_records]
    placeholders = ','.join(['?' for _ in reserve_numbers])
    
    lms_cur.execute(f"""
        SELECT Reserve_No, Date_Entered, PU_Date
        FROM Reserve
        WHERE Reserve_No IN ({placeholders})
        ORDER BY Reserve_No
    """, reserve_numbers)
    
    lms_creation_dates = {}
    print(f"{'Reserve':<10} {'LMS Date Entered':<20} {'LMS PU_Date':<20}")
    print("-" * 80)
    
    for reserve, date_entered, pu_date in lms_cur.fetchall()[:10]:
        entered_str = date_entered.strftime('%Y-%m-%d %H:%M:%S') if date_entered else 'NULL'
        pu_str = pu_date.strftime('%Y-%m-%d %H:%M:%S') if pu_date else 'NULL'
        print(f"{reserve:<10} {entered_str:<20} {pu_str:<20}")
        
        if date_entered:
            entered_date = date_entered.date()
            lms_creation_dates[entered_date] = lms_creation_dates.get(entered_date, 0) + 1
    
    print(f"... (showing first 10 of {len(reserve_numbers)})")
    print()
    
    if lms_creation_dates:
        print("LMS Date_Entered distribution:")
        for date, count in sorted(lms_creation_dates.items(), key=lambda x: x[1], reverse=True):
            print(f"  {date}: {count} charters")
    print()
    
    # Check for 2025-08-06 in other tables/scripts
    print("SEARCHING FOR 2025-08-06 HARDCODED DATE:")
    print("-" * 80)
    
    # Check if any scripts use this date
    import os
    import re
    
    scripts_dir = r'L:\limo\scripts'
    found_matches = []
    
    for filename in os.listdir(scripts_dir):
        if filename.endswith('.py'):
            filepath = os.path.join(scripts_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if '2025-08-06' in content or '2025/08/06' in content or '08-06-2025' in content:
                        found_matches.append(filename)
            except Exception:
                pass
    
    if found_matches:
        print("Scripts containing '2025-08-06':")
        for script in found_matches:
            print(f"  - {script}")
    else:
        print("No scripts found with hardcoded 2025-08-06 date")
    print()
    
    # Hypothesis summary
    print("HYPOTHESIS:")
    print("-" * 80)
    print("Based on the analysis:")
    print()
    print("1. All 39 charters (019669-019707) are sequential reserve numbers")
    print("2. This suggests a single batch import operation")
    print("3. Check if created_at timestamps cluster on a single date")
    print("4. The date 2025-08-06 may have been:")
    print("   - Hardcoded in an import script")
    print("   - Set to CURRENT_DATE during import on that date")
    print("   - Result of a failed date field mapping")
    print()
    print("ROOT CAUSE LIKELY:")
    print("An import script run on or around 2025-08-06 that failed to properly")
    print("map LMS PU_Date field to PostgreSQL charter_date field, instead using")
    print("a default value or the current date at time of import.")
    
    pg_cur.close()
    lms_cur.close()
    pg_conn.close()
    lms_conn.close()

if __name__ == '__main__':
    main()
