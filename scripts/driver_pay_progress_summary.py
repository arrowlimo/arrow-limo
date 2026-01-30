"""
Summary of driver pay ingestion progress and next steps
"""
import os
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    print("="*80)
    print("DRIVER PAY INGESTION - PROGRESS SUMMARY")
    print("="*80)
    print()
    
    # Overall status
    cur.execute("""
        SELECT status, COUNT(*) 
        FROM staging_driver_pay_files 
        GROUP BY status
        ORDER BY status
    """)
    
    print("FILE STATUS:")
    print("-"*80)
    total_files = 0
    for status, count in cur.fetchall():
        total_files += count
        print(f"  {status:20s}: {count:6d} files")
    print(f"  {'TOTAL':20s}: {total_files:6d} files")
    print()
    
    # Records loaded
    cur.execute("SELECT COUNT(*) FROM staging_driver_pay")
    record_count = cur.fetchone()[0]
    print(f"Records loaded: {record_count:,}")
    print()
    
    # Exclusion breakdown
    cur.execute("""
        SELECT error_message, COUNT(*) 
        FROM staging_driver_pay_files 
        WHERE status = 'excluded'
        GROUP BY error_message
        ORDER BY COUNT(*) DESC
    """)
    
    print("EXCLUDED FILE REASONS:")
    print("-"*80)
    for reason, count in cur.fetchall():
        print(f"  [{count:3d}] {reason[:70]}")
    print()
    
    # Remaining errors by pattern
    cur.execute("""
        SELECT 
            CASE 
                WHEN error_message LIKE '%Excel file format%' THEN 'Excel format error'
                WHEN error_message LIKE '%NaT%' THEN 'Date parsing (NaT)'
                WHEN error_message LIKE '%encoding%' THEN 'Encoding error'
                WHEN error_message LIKE '%PDF%' THEN 'PDF parsing error'
                ELSE 'Other error'
            END as error_type,
            COUNT(*)
        FROM staging_driver_pay_files 
        WHERE status = 'error'
        GROUP BY error_type
        ORDER BY COUNT(*) DESC
    """)
    
    print("REMAINING ERROR BREAKDOWN:")
    print("-"*80)
    for error_type, count in cur.fetchall():
        print(f"  [{count:3d}] {error_type}")
    print()
    
    # Identify likely driver pay files in errors
    cur.execute("""
        SELECT file_name, error_message
        FROM staging_driver_pay_files 
        WHERE status = 'error'
          AND (lower(file_name) LIKE '%payroll%'
            OR lower(file_name) LIKE '%pay%cheque%'
            OR lower(file_name) LIKE '%pay%stub%'
            OR lower(file_name) LIKE '%vacation%pay%'
            OR lower(file_name) LIKE '%hourly%')
        ORDER BY file_name
        LIMIT 30
    """)
    
    likely_pay_files = cur.fetchall()
    print(f"LIKELY DRIVER PAY FILES STILL IN ERROR ({len(likely_pay_files)} found):")
    print("-"*80)
    for file_name, error_msg in likely_pay_files:
        error_short = error_msg.split('\n')[0][:60]
        print(f"  {file_name}")
        print(f"    Error: {error_short}")
    print()
    
    print("="*80)
    print("NEXT STEPS:")
    print("="*80)
    print("1. Fix Excel format errors - upgrade openpyxl or try xlrd")
    print("2. Improve date parsing - infer dates from filenames")
    print("3. Manual review remaining unclear files")
    print("4. Validate/deduplicate loaded records")
    print("5. Cross-reference with charter activity")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
