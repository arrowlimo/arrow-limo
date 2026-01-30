#!/usr/bin/env python3
import os
import glob
import psycopg2

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432')),
    'dbname': os.environ.get('DB_NAME', 'almsdata'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '***REDACTED***'),
}

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'migrations')


def run_sql(cur, sql_text: str):
    for stmt in [s.strip() for s in sql_text.split(';') if s.strip()]:
        cur.execute(stmt)


def main():
    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, '*.sql')))
    if not files:
        print('No migrations found')
        return
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    applied = 0
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                sql_text = fh.read()
            print(f'Applying: {os.path.basename(f)}')
            run_sql(cur, sql_text)
            conn.commit()
            applied += 1
        except Exception as e:
            conn.rollback()
            print(f'WARN: Failed to apply {f}: {e}')
    cur.close(); conn.close()
    print(f'Done. Applied {applied} migration files.')

if __name__ == '__main__':
    main()
