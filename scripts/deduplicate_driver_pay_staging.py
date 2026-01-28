import psycopg2
import os

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
    # Find duplicates by concatenating key columns
    cur.execute('''
        SELECT MIN(id) as keep_id, ARRAY_AGG(id) as duplicate_ids
        FROM staging_driver_pay
        GROUP BY file_id, source_row_id, source_line_no, txn_date, driver_name, amount, memo, check_no, account, category, vendor, source_sheet, source_file
        HAVING COUNT(*) > 1
    ''')
    dups = cur.fetchall()
    print(f"Found {len(dups)} duplicate groups.")
    removed = 0
    for keep_id, ids in dups:
        ids_to_remove = [i for i in ids if i != keep_id]
        if ids_to_remove:
            cur.execute('DELETE FROM staging_driver_pay WHERE id = ANY(%s)', (ids_to_remove,))
            removed += len(ids_to_remove)
    conn.commit()
    print(f"Removed {removed} duplicate records.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
