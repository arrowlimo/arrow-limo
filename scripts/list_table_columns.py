import sys, os
import psycopg2

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def main():
    if len(sys.argv) < 2:
        print("Usage: list_table_columns.py <table>")
        return 2
    table = sys.argv[1]
    with psycopg2.connect(**DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            cols = [r[0] for r in cur.fetchall()]
            print(f"{table} columns ({len(cols)}):")
            for c in cols:
                print(" -", c)

if __name__ == "__main__":
    main()
