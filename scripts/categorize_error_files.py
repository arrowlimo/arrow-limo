"""
This script re-processes error files with improved parsing:
1. Handle NaT dates by inferring from filename or context
2. Skip non-transactional data (summaries, reports, lists)
3. Better identification of actual driver pay records
"""
import os
import re
import psycopg2
import pandas as pd
from datetime import datetime

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def categorize_file(file_path, file_name):
    """Determine if file should be excluded based on name patterns"""
    lower_name = file_name.lower()
    
    # Exclude patterns - not driver pay data
    exclude_patterns = [
        'account history', 'account list', 'transactions without',
        'leasing summary', 'driver info', 'employee earnings sum',
        'employee contact', 'rate', 'book1', 'book2', 'book3', 'book4', 'book5',
        'cibc', 'bank', 'summary', 'list', 'report'
    ]
    
    for pattern in exclude_patterns:
        if pattern in lower_name:
            return 'exclude', f'Reference/summary document: {pattern}'
    
    # Keep patterns - likely driver pay
    keep_patterns = [
        'payroll', 'pay cheque', 'pay check', 'driver pay', 'hourly',
        'weekly', 'bi-weekly', 'wages'
    ]
    
    for pattern in keep_patterns:
        if pattern in lower_name:
            return 'retry', 'Likely driver pay data'
    
    # Check for date patterns in filename (e.g., "2Apr", "Mar.2014")
    if re.search(r'\d{1,2}(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', lower_name):
        return 'retry', 'Date in filename suggests transactional data'
    
    # Default: needs manual review
    return 'review', 'Unclear if driver pay data'

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    # Get error files
    cur.execute("""
        SELECT id, file_path, file_name, file_type
        FROM staging_driver_pay_files
        WHERE status = 'error'
        ORDER BY file_path
    """)
    
    error_files = cur.fetchall()
    
    stats = {
        'excluded': 0,
        'retry': 0,
        'review': 0
    }
    
    exclude_list = []
    retry_list = []
    review_list = []
    
    for file_id, file_path, file_name, file_type in error_files:
        category, reason = categorize_file(file_path, file_name)
        
        if category == 'exclude':
            exclude_list.append((file_id, file_name, reason))
            stats['excluded'] += 1
        elif category == 'retry':
            retry_list.append((file_id, file_name, reason))
            stats['retry'] += 1
        else:
            review_list.append((file_id, file_name, reason))
            stats['review'] += 1
    
    # Mark excluded files
    for file_id, file_name, reason in exclude_list:
        cur.execute("""
            UPDATE staging_driver_pay_files
            SET status = 'excluded', error_message = %s
            WHERE id = %s
        """, (f'Auto-excluded: {reason}', file_id))
    
    conn.commit()
    
    print("=" * 80)
    print("ERROR FILE CATEGORIZATION")
    print("=" * 80)
    print(f"Total error files: {len(error_files)}")
    print(f"  Auto-excluded: {stats['excluded']}")
    print(f"  Retry parsing: {stats['retry']}")
    print(f"  Manual review: {stats['review']}")
    print()
    
    # Show samples
    print("\nAUTO-EXCLUDED (first 20):")
    print("-" * 80)
    for file_id, file_name, reason in exclude_list[:20]:
        print(f"  {file_name}")
        print(f"    Reason: {reason}")
    
    print(f"\nRETRY PARSING (first 20):")
    print("-" * 80)
    for file_id, file_name, reason in retry_list[:20]:
        print(f"  {file_name}")
        print(f"    Reason: {reason}")
    
    print(f"\nMANUAL REVIEW NEEDED (first 20):")
    print("-" * 80)
    for file_id, file_name, reason in review_list[:20]:
        print(f"  {file_name}")
        print(f"    Reason: {reason}")
    
    # Save lists to files
    with open("driver_pay_excluded_files.txt", "w", encoding="utf-8") as f:
        f.write("AUTO-EXCLUDED FILES\n")
        f.write("=" * 80 + "\n\n")
        for file_id, file_name, reason in exclude_list:
            f.write(f"{file_name}\n  Reason: {reason}\n\n")
    
    with open("driver_pay_retry_files.txt", "w", encoding="utf-8") as f:
        f.write("FILES TO RETRY PARSING\n")
        f.write("=" * 80 + "\n\n")
        for file_id, file_name, reason in retry_list:
            f.write(f"{file_name}\n  Reason: {reason}\n\n")
    
    with open("driver_pay_review_files.txt", "w", encoding="utf-8") as f:
        f.write("FILES NEEDING MANUAL REVIEW\n")
        f.write("=" * 80 + "\n\n")
        for file_id, file_name, reason in review_list:
            f.write(f"{file_name}\n  Reason: {reason}\n\n")
    
    cur.close()
    conn.close()
    
    print("\nFiles saved:")
    print("  - driver_pay_excluded_files.txt")
    print("  - driver_pay_retry_files.txt")
    print("  - driver_pay_review_files.txt")

if __name__ == '__main__':
    main()
