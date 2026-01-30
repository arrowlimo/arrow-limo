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
    
    # Find payroll Excel files
    cur.execute("""
        SELECT file_path, file_name FROM staging_driver_pay_files 
        WHERE lower(file_name) LIKE '%payroll%' AND file_type IN ('xls', 'xlsx') 
        ORDER BY file_name LIMIT 20
    """)
    print("PAYROLL EXCEL FILES:")
    print("="*80)
    for fp, fn in cur.fetchall():
        print(f"{fn}\n  Path: {fp}\n")
    
    # Exclude Accounts Payable Workbook files
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET status = 'excluded', error_message = 'Manually excluded: Accounts Payable workbook, not driver pay data'
        WHERE lower(file_name) LIKE '%accounts%payable%workbook%'
    """)
    print(f"\nExcluded {cur.rowcount} Accounts Payable Workbook files.")
    
    # Exclude AB Employment Standards Code
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET status = 'excluded', error_message = 'Manually excluded: Employment Standards Code reference book'
        WHERE lower(file_name) LIKE '%ab%employment%stds%code%' OR lower(file_name) LIKE '%employment%standards%code%'
    """)
    print(f"Excluded {cur.rowcount} Employment Standards Code files.")
    
    # Confirm 2Mar.2014 Pay Cheques.pdf is marked as pay stub
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET file_type = 'pay_stub'
        WHERE lower(file_name) LIKE '%2mar.2014%pay%cheque%'
    """)
    print(f"Confirmed {cur.rowcount} files marked as pay stub (2Mar.2014 Pay Cheques.pdf).")
    
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
