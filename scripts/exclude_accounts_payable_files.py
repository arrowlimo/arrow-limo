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
    
    files_to_exclude = [
        r"L:\limo\quickbooks\New folder\Accounts Payable listing as of Jan 1 2011.xls",
        r"L:\limo\quickbooks\New folder\Accounts Payable Workbook 2012.xls",
        r"L:\limo\quickbooks\New folder\Accounts Payable Workbook 2014.xls"
    ]
    
    for file_path in files_to_exclude:
        cur.execute("""
            UPDATE staging_driver_pay_files
            SET status = 'excluded', 
                error_message = 'Manually excluded: Accounts Payable listing/workbook, not driver pay data'
            WHERE file_path = %s
        """, (file_path,))
        print(f"Excluded: {os.path.basename(file_path)}")
    
    conn.commit()
    print(f"\nTotal excluded: {len(files_to_exclude)} Accounts Payable files")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
