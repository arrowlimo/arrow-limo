import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

MIGRATIONS = [
    "migrations/2025-12-27_add_vendor_performance_indexes.sql",
    "migrations/2025-12-27_create_vendor_synonyms.sql",
    "migrations/2025-12-27_vendor_account_enhancements.sql",
]

def run_migration(conn, filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        print(f"✅ Applied: {filepath}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed: {filepath} - {e}")
        raise
    finally:
        cur.close()

def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    try:
        for mig in MIGRATIONS:
            run_migration(conn, mig)
        print("\n✅ All vendor account migrations applied successfully")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
