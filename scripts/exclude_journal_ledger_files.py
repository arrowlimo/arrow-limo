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
        SET status = 'excluded', error_message = 'Manually excluded: journal/ledger file, not driver pay data'
        WHERE lower(file_name) LIKE '%journal%' OR lower(file_name) LIKE '%ledger%'
    """)
    print(f"Marked all journal/ledger files as excluded.")
    conn.commit()
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
