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
    
    print("=" * 120)
    print("FILES WITH ERRORS - FULL LIST")
    print("=" * 120)
    
    cur.execute("""
        SELECT file_path, file_name, file_type, error_message
        FROM staging_driver_pay_files
        WHERE status = 'error'
        ORDER BY file_type, file_name
    """)
    
    errors_by_type = {}
    for row in cur.fetchall():
        file_path, file_name, file_type, error_message = row
        if file_type not in errors_by_type:
            errors_by_type[file_type] = []
        errors_by_type[file_type].append((file_path, file_name, error_message))
    
    for file_type in sorted(errors_by_type.keys()):
        print(f"\n{'='*120}")
        print(f"FILE TYPE: {file_type.upper()}")
        print(f"{'='*120}")
        files = errors_by_type[file_type]
        print(f"Total: {len(files)} files\n")
        
        for file_path, file_name, error_message in files:
            print(f"File: {file_path}")
            print(f"Error: {error_message[:200]}")
            print("-" * 120)
    
    # Summary by error type
    print(f"\n{'='*120}")
    print("ERROR SUMMARY BY TYPE")
    print(f"{'='*120}")
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN error_message LIKE '%Excel file format%' THEN 'Excel Format Error'
                WHEN error_message LIKE '%invalid input syntax for type timestamp%' THEN 'Timestamp NaT Error'
                WHEN error_message LIKE '%syntax error%' THEN 'XML/QBO Syntax Error'
                WHEN error_message LIKE '%codec%' THEN 'Encoding Error'
                WHEN error_message LIKE '%not in index%' THEN 'Missing Column Error'
                WHEN error_message LIKE '%PDF%' THEN 'PDF Parse Error'
                ELSE 'Other Error'
            END as error_type,
            COUNT(*) as count
        FROM staging_driver_pay_files
        WHERE status = 'error'
        GROUP BY error_type
        ORDER BY count DESC
    """)
    
    for row in cur.fetchall():
        print(f"{row[0]:30s} {row[1]:5d} files")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
