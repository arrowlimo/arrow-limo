import os
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    # Exclude summary/reference documents
    exclude_patterns = [
        ('%employee%earnings%summary%', 'year-end summary'),
        ('%employee%earnings%sum%', 'year-end summary'),
        ('%account%history%', 'account history report'),
        ('%account%list%', 'chart of accounts'),
        ('%transactions%without%', 'transaction report'),
        ('%leasing%summary%', 'leasing summary report'),
        ('%driver%info%', 'driver information list'),
        ('%employee%contact%', 'employee contact list'),
        ('%employee%list%', 'employee list'),
        ('%book1%', 'template/test file'),
        ('%book2%', 'template/test file'),
        ('%book3%', 'template/test file'),
        ('%book4%', 'template/test file'),
        ('%book5%', 'template/test file'),
        ('%cibc%test%', 'test file'),
        ('%summary%', 'summary report')
    ]
    
    total_excluded = 0
    
    for pattern, reason in exclude_patterns:
        cur.execute("""
            UPDATE staging_driver_pay_files
            SET status = 'excluded', 
                error_message = %s
            WHERE lower(file_name) LIKE %s
              AND status = 'error'
        """, (f'Auto-excluded: {reason} - not transactional driver pay data', pattern))
        
        count = cur.rowcount
        if count > 0:
            total_excluded += count
            print(f"Excluded {count:3d} files matching pattern: {pattern}")
    
    conn.commit()
    
    # Show updated summary
    cur.execute("""
        SELECT status, COUNT(*) 
        FROM staging_driver_pay_files 
        GROUP BY status
        ORDER BY status
    """)
    
    print("\n" + "="*80)
    print("UPDATED FILE STATUS SUMMARY")
    print("="*80)
    for status, count in cur.fetchall():
        print(f"{status:20s}: {count:6d} files")
    
    print(f"\nTotal auto-excluded this run: {total_excluded}")
    
    # Show remaining error files count by type
    cur.execute("""
        SELECT file_type, COUNT(*) 
        FROM staging_driver_pay_files 
        WHERE status = 'error'
        GROUP BY file_type
        ORDER BY file_type
    """)
    
    print("\n" + "="*80)
    print("REMAINING ERROR FILES BY TYPE")
    print("="*80)
    remaining = cur.fetchall()
    for file_type, count in remaining:
        print(f"{file_type:10s}: {count:4d} files")
    
    # Show sample of remaining error files
    cur.execute("""
        SELECT file_name, error_message
        FROM staging_driver_pay_files 
        WHERE status = 'error'
        ORDER BY file_name
        LIMIT 20
    """)
    
    print("\n" + "="*80)
    print("SAMPLE OF REMAINING ERROR FILES (first 20)")
    print("="*80)
    for file_name, error_msg in cur.fetchall():
        print(f"\nFile: {file_name}")
        print(f"Error: {error_msg[:100]}...")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
