import os
import sys
import argparse
import psycopg2


def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def execute_sql_file(cur, path):
    with open(path, 'r', encoding='utf-8') as f:
        sql = f.read()
    # Use autocommit and execute the whole file; handles DO $$ ... $$ blocks
    cur.execute(sql)


def main():
    parser = argparse.ArgumentParser(description='Apply a SQL migration file to PostgreSQL')
    parser.add_argument('--file', required=True, help='Path to .sql file')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"File not found: {args.file}")
        sys.exit(1)

    conn = get_conn()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        print(f"Applying: {args.file}")
        execute_sql_file(cur, args.file)
        print("✓ Migration applied")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
