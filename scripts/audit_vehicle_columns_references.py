import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_conn():
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_NAME = os.environ.get("DB_NAME", "almsdata")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def list_tables_with_columns(cur, column_names):
    q = """
    SELECT table_schema, table_name, column_name
    FROM information_schema.columns
    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
      AND column_name = ANY(%s)
    ORDER BY table_schema, table_name, column_name;
    """
    cur.execute(q, (column_names,))
    return cur.fetchall()

def list_fk_to_vehicles(cur):
    q = """
    SELECT
      tc.table_schema,
      tc.table_name,
      kcu.column_name,
      ccu.table_schema AS foreign_table_schema,
      ccu.table_name AS foreign_table_name,
      ccu.column_name AS foreign_column_name,
      tc.constraint_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND ccu.table_name = 'vehicles';
    """
    cur.execute(q)
    return cur.fetchall()

def list_vehicles_columns(cur):
    q = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'vehicles'
    ORDER BY ordinal_position;
    """
    cur.execute(q)
    return cur.fetchall()

if __name__ == "__main__":
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            print("# vehicles table columns:")
            for col in list_vehicles_columns(cur):
                print(f"- {col['column_name']} ({col['data_type']})")
            print("")

            cols = ['vehicle_number', 'fleet_number']
            print("# Tables containing 'vehicle_number' or 'fleet_number':")
            rows = list_tables_with_columns(cur, cols)
            for r in rows:
                print(f"- {r['table_schema']}.{r['table_name']} -> {r['column_name']}")
            print("")

            print("# Foreign keys referencing vehicles:")
            for fk in list_fk_to_vehicles(cur):
                print(f"- {fk['table_schema']}.{fk['table_name']}({fk['column_name']}) -> {fk['foreign_table_schema']}.{fk['foreign_table_name']}({fk['foreign_column_name']}) [constraint: {fk['constraint_name']}]")
            print("")

            # Quick counts where applicable
            try:
                cur.execute("SELECT COUNT(*) FROM receipts WHERE vehicle_number IS NOT NULL AND vehicle_number <> '';")
                count_receipts = cur.fetchone()['count']
                print(f"# receipts.vehicle_number non-empty rows: {count_receipts}")
            except Exception as e:
                print(f"# receipts check skipped: {e}")

            try:
                cur.execute("SELECT COUNT(*) FROM vehicles WHERE fleet_number IS NOT NULL AND fleet_number <> '';")
                count_fleet = cur.fetchone()['count']
                print(f"# vehicles.fleet_number non-empty rows: {count_fleet}")
            except Exception as e:
                print(f"# vehicles.fleet_number check skipped: {e}")
