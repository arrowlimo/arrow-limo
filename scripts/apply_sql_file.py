"""
Apply a .sql file to the Postgres database using psycopg2.

Usage:
  python -X utf8 l:\limo\scripts\apply_sql_file.py --file l:\limo\migrations\2025-12-19_lock_banking_completed_years.sql
"""
import argparse
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True, help='Path to SQL file to apply')
    args = parser.parse_args()

    with open(args.file, 'r', encoding='utf-8') as f:
        sql = f.read()

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        print(f"✅ Applied migration: {args.file}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to apply migration: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Apply a SQL file to the configured Postgres database using psycopg2.

Usage:
  python scripts/apply_sql_file.py --file migrations/2025-10-11_create_lms_unified_views.sql
"""
import os
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

def main():
    ap = argparse.ArgumentParser(description='Apply a SQL file to Postgres')
    ap.add_argument('--file', required=True, help='Path to .sql file')
    args = ap.parse_args()

    path = args.file
    if not os.path.exists(path):
        print(f"SQL file not found: {path}")
        return 1

    sql = open(path, 'r', encoding='utf-8').read()
    if not sql.strip():
        print(f"SQL file is empty: {path}")
        return 1

    with psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            conn.commit()
            print(f"Applied SQL successfully: {path}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
