import os
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

EXCLUDE_PATHS = [
    r"L:\\limo\\quickbooks\\New folder\\general ledger2.csv",
    r"L:\\limo\\quickbooks\\New folder\\journal 2025.CSV"
]

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    for path in EXCLUDE_PATHS:
        cur.execute("""
            UPDATE staging_driver_pay_files
            SET status = 'excluded', error_message = 'Manually excluded: not driver pay data'
            WHERE file_path = %s
        """, (path,))
        print(f"Marked as excluded: {path}")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
