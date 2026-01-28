import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

SQL_PATH = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
                        "migrations", "2025-12-27_create_vendor_accounts.sql")

def main():
    with open(SQL_PATH, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        print("✅ Vendor accounts schema applied")
    except Exception as e:
        conn.rollback()
        print(f"❌ Failed to apply schema: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
