import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

FILES = [
    'migrations/2025-09-18_add_is_placeholder_and_view.sql',
    'migrations/2025-09-18_backfill_is_placeholder.sql',
]

def run_sql_file(cur, path):
    with open(path, 'r', encoding='utf-8') as f:
        sql = f.read()
    cur.execute(sql)


def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        for f in FILES:
            print(f"Applying {f} ...")
            run_sql_file(cur, f)
        conn.commit()
        print("Migrations applied.")
    except Exception as e:
        conn.rollback()
        print("Migration failed:", e)
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
