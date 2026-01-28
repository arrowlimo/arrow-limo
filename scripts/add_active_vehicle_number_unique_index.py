import os
import psycopg2

def get_conn():
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", "almsdata")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

INDEX_NAME = "uniq_active_vehicle_number"

SQL_CREATE_INDEX = f"""
CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
ON public.vehicles (vehicle_number)
WHERE is_active = TRUE AND decommission_date IS NULL;
"""

SQL_CHECK_INDEX = """
SELECT 1
FROM pg_indexes
WHERE schemaname = 'public' AND indexname = %s;
"""

if __name__ == "__main__":
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SQL_CHECK_INDEX, (INDEX_NAME,))
            exists = cur.fetchone() is not None
            if exists:
                print(f"Index already exists: {INDEX_NAME}")
            else:
                cur.execute(SQL_CREATE_INDEX)
                conn.commit()
                print(f"Created index: {INDEX_NAME}")
