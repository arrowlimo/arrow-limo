import os
import psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM charters")
        total_charters = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM charters WHERE assigned_driver_id IS NOT NULL")
        charters_with_assigned = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM charters c
            JOIN employees e ON e.employee_id = c.assigned_driver_id
        """)
        charters_linked_to_existing_employees = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT assigned_driver_id) FROM charters WHERE assigned_driver_id IS NOT NULL")
        distinct_assigned_ids = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT c.assigned_driver_id)
            FROM charters c
            JOIN employees e ON e.employee_id = c.assigned_driver_id
            WHERE c.assigned_driver_id IS NOT NULL
        """)
        distinct_existing_driver_ids = cur.fetchone()[0]

        print("Total charters:", total_charters)
        print("Charters with any assigned_driver_id:", charters_with_assigned)
        print("Charters linked to existing employees:", charters_linked_to_existing_employees)
        print("Distinct assigned_driver_id values (any):", distinct_assigned_ids)
        print("Distinct assigned drivers (existing employees):", distinct_existing_driver_ids)
