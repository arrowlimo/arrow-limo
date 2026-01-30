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
    
    print("=" * 80)
    print("DRIVER PAY INGESTION STATUS REPORT")
    print("=" * 80)
    
    # File summary
    cur.execute("""
        SELECT status, COUNT(*) as count, SUM(rows_parsed) as total_rows
        FROM staging_driver_pay_files
        GROUP BY status
        ORDER BY status
    """)
    print("\n--- FILE PROCESSING STATUS ---")
    for row in cur.fetchall():
        print(f"{row[0]:20s} {row[1]:5d} files    {row[2] or 0:8d} rows")
    
    # Total records in staging
    cur.execute("SELECT COUNT(*) FROM staging_driver_pay")
    total_records = cur.fetchone()[0]
    print(f"\nTotal records in staging_driver_pay: {total_records:,}")
    
    # Date range
    cur.execute("""
        SELECT MIN(txn_date), MAX(txn_date), COUNT(*) as with_dates
        FROM staging_driver_pay
        WHERE txn_date IS NOT NULL
    """)
    row = cur.fetchone()
    if row[0]:
        print(f"Date range: {row[0]} to {row[1]} ({row[2]:,} records with dates)")
    
    # Pay types
    cur.execute("""
        SELECT pay_type, COUNT(*) as count
        FROM staging_driver_pay
        GROUP BY pay_type
        ORDER BY count DESC
    """)
    print("\n--- RECORDS BY PAY TYPE ---")
    for row in cur.fetchall():
        print(f"{row[0] or '(null)':20s} {row[1]:8d}")
    
    # Driver names found
    cur.execute("""
        SELECT driver_name, COUNT(*) as count, SUM(amount) as total_amount
        FROM staging_driver_pay
        WHERE driver_name IS NOT NULL AND amount IS NOT NULL
        GROUP BY driver_name
        ORDER BY total_amount DESC NULLS LAST
        LIMIT 20
    """)
    print("\n--- TOP 20 DRIVERS BY AMOUNT ---")
    for row in cur.fetchall():
        print(f"{row[0]:40s} {row[1]:5d} records    ${row[2]:12,.2f}")
    
    # Files with errors
    cur.execute("""
        SELECT file_name, error_message
        FROM staging_driver_pay_files
        WHERE status = 'error'
        ORDER BY file_name
        LIMIT 10
    """)
    print("\n--- SAMPLE OF FILES WITH ERRORS (first 10) ---")
    for row in cur.fetchall():
        err = row[1][:60] if row[1] else 'Unknown'
        print(f"{row[0]:50s} {err}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
