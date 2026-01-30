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
        SET status = 'excluded', error_message = 'Manually excluded: Employee Standards Code reference book, not pay data.'
        WHERE lower(file_name) LIKE '%employee%standards%code%'
    """)
    print(f"Marked all Employee Standards Code files as excluded.")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
