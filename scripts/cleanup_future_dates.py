"""
Clean Future-Dated Journal Entries
These are loan schedules and bad imports, not actual transactions
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )

def analyze_future_dates(conn):
    """Analyze future-dated entries before cleanup"""
    print("\n" + "="*80)
    print("ANALYZING FUTURE-DATED ENTRIES (2026-2031)")
    print("="*80)
    
    cur = conn.cursor()
    
    # Count by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as count
        FROM qb_journal_entries
        WHERE EXTRACT(YEAR FROM transaction_date) >= 2026
        GROUP BY year
        ORDER BY year
    """)
    
    print("\nCount by Year:")
    total_future = 0
    for year, count in cur.fetchall():
        print(f"  {int(year)}: {count} entries")
        total_future += count
    
    print(f"\nTotal future-dated entries: {total_future}")
    
    # Analyze by source
    cur.execute("""
        SELECT 
            source_file,
            COUNT(*) as count,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest
        FROM qb_journal_entries
        WHERE EXTRACT(YEAR FROM transaction_date) >= 2026
        GROUP BY source_file
        ORDER BY count DESC
    """)
    
    print("\nBy Source File:")
    for source, count, earliest, latest in cur.fetchall():
        print(f"  {source}: {count} entries ({earliest} to {latest})")
    
    # Check for Square Capital loans (automatic payments)
    cur.execute("""
        SELECT COUNT(*)
        FROM qb_journal_entries
        WHERE EXTRACT(YEAR FROM transaction_date) >= 2026
        AND description LIKE '%Automatic payment%'
    """)
    loan_count = cur.fetchone()[0]
    print(f"\nSquare Capital loan schedules: {loan_count} entries")
    
    # Check for empty entries
    cur.execute("""
        SELECT COUNT(*)
        FROM qb_journal_entries
        WHERE EXTRACT(YEAR FROM transaction_date) >= 2026
        AND account_code IS NULL
        AND debit_amount IS NULL
        AND credit_amount IS NULL
        AND amount IS NULL
    """)
    empty_count = cur.fetchone()[0]
    print(f"Empty/invalid entries: {empty_count} entries")
    
    cur.close()
    return total_future, loan_count, empty_count

def cleanup_future_dates(conn, dry_run=True):
    """Clean up future-dated entries"""
    print("\n" + "="*80)
    if dry_run:
        print("DRY RUN - Showing what would be deleted")
    else:
        print("DELETING FUTURE-DATED ENTRIES")
    print("="*80)
    
    cur = conn.cursor()
    
    if dry_run:
        # Just show what would be deleted
        cur.execute("""
            SELECT 
                staging_id,
                transaction_date,
                source_file,
                description,
                amount
            FROM qb_journal_entries
            WHERE EXTRACT(YEAR FROM transaction_date) >= 2026
            ORDER BY transaction_date
            LIMIT 20
        """)
        
        print("\nSample entries to be deleted:")
        for staging_id, date, source, desc, amt in cur.fetchall():
            print(f"  ID {staging_id}: {date} | {source} | {desc or '(empty)'} | ${amt or 0}")
        
        cur.execute("""
            SELECT COUNT(*)
            FROM qb_journal_entries
            WHERE EXTRACT(YEAR FROM transaction_date) >= 2026
        """)
        total = cur.fetchone()[0]
        print(f"\nTotal entries that would be deleted: {total}")
        
    else:
        # Actually delete
        cur.execute("""
            DELETE FROM qb_journal_entries
            WHERE EXTRACT(YEAR FROM transaction_date) >= 2026
        """)
        deleted = cur.rowcount
        conn.commit()
        print(f"\n✓ Deleted {deleted} future-dated entries")
    
    cur.close()

def verify_cleanup(conn):
    """Verify cleanup completed"""
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    cur = conn.cursor()
    
    # Check date range
    cur.execute("""
        SELECT 
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest,
            COUNT(*) as total
        FROM qb_journal_entries
    """)
    
    earliest, latest, total = cur.fetchone()
    print(f"\nCurrent date range: {earliest} to {latest}")
    print(f"Total entries: {total:,}")
    
    # Check for any remaining future dates
    cur.execute("""
        SELECT COUNT(*)
        FROM qb_journal_entries
        WHERE transaction_date > CURRENT_DATE
    """)
    
    future_count = cur.fetchone()[0]
    if future_count > 0:
        print(f"\n[WARN]  Warning: Still {future_count} future-dated entries")
    else:
        print(f"\n✓ No future-dated entries remaining")
    
    cur.close()

def main():
    print("\n" + "="*80)
    print("FUTURE-DATED JOURNAL ENTRIES CLEANUP")
    print("="*80)
    
    print("""
ISSUE: Found 99 journal entries dated 2026-2031

CAUSE: These are NOT actual transactions:
  1. Square Capital loan repayment schedules (automatic payments)
  2. Bad data from CSV imports (Reserve2.csv, invalid_charter_dates.csv)
  
SOLUTION: Delete these future-dated entries
  - They are loan schedules, not actual transactions
  - Empty records from invalid imports
  - Should only have transactions up to current date (2025)
    """)
    
    conn = get_db_connection()
    
    try:
        # Analyze
        total_future, loan_count, empty_count = analyze_future_dates(conn)
        
        # Dry run first
        cleanup_future_dates(conn, dry_run=True)
        
        # Ask for confirmation
        print("\n" + "="*80)
        response = input("\nDelete these entries? (yes/no): ").strip().lower()
        
        if response == 'yes':
            cleanup_future_dates(conn, dry_run=False)
            verify_cleanup(conn)
            print("\n✓ Cleanup complete!")
        else:
            print("\nCleanup cancelled. No changes made.")
            
    finally:
        conn.close()

if __name__ == '__main__':
    main()
