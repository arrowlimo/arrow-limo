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
    cur.execute("""
        UPDATE staging_driver_pay_files
        SET file_type = 'pay_stub', error_message = COALESCE(error_message, '') || ' | Marked as pay stub (filename contains check)'
        WHERE lower(file_name) LIKE '%check%' OR lower(file_name) LIKE '%cheque%' OR lower(file_name) LIKE '%ck%'
    """)
    print(f"Marked all files with 'check', 'cheque', or 'ck' in the name as pay stubs.")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
