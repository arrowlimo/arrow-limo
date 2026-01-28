import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT c.column_name, c.data_type, c.is_nullable, c.character_maximum_length,
               c.column_default
        FROM information_schema.columns c
        WHERE c.table_schema = 'public' AND c.table_name = 'charters'
        ORDER BY c.ordinal_position
        """
    )
    cols = cur.fetchall()
    print("charters columns:")
    for name, dtype, nullable, maxlen, default in cols:
        print(f"- {name} | {dtype} | nullable={nullable} | maxlen={maxlen}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
