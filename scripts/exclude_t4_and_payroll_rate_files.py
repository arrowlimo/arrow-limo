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
    
    # Exclude T4 files (tax forms, year-end summaries)
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET status = 'excluded', 
            error_message = 'Manually excluded: T4 tax form - validation/reference document, not transactional data'
        WHERE lower(file_name) LIKE '%t4%'
    """)
    t4_count = cur.rowcount
    print(f"Marked {t4_count} T4 files as excluded.")
    
    # Exclude payroll rate files (rate schedules, employee lists)
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET status = 'excluded', 
            error_message = 'Manually excluded: payroll rate schedule - reference document, not transactional data'
        WHERE lower(file_name) LIKE '%payroll%rate%' 
           OR lower(file_name) LIKE '%employee%contact%'
           OR lower(file_name) LIKE '%employee%list%'
           OR lower(file_name) LIKE '%rate%schedule%'
    """)
    rate_count = cur.rowcount
    print(f"Marked {rate_count} payroll rate/employee list files as excluded.")
    
    conn.commit()
    
    # Show summary
    cur.execute("""
        SELECT status, COUNT(*) 
        FROM staging_driver_pay_files 
        GROUP BY status
        ORDER BY status
    """)
    print("\n" + "="*60)
    print("File Status Summary:")
    print("="*60)
    for status, count in cur.fetchall():
        print(f"{status:20s}: {count:6d} files")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
