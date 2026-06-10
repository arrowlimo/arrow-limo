from ...db import get_connection


def get_employee_role(employee_id: int) -> str:
    """Load employee role for dashboard routing decisions."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT role FROM employees WHERE employee_id = %s", (employee_id,))
        role_row = cur.fetchone()
        cur.close()
        conn.close()
        return role_row[0] if role_row else "user"
    except Exception:
        return "user"


def get_driver_trips(employee_id: int) -> list:
    """Fetch today's trips for driver/operator dashboard."""
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                charter_id,
                reserve_number,
                pickup_address,
                dropoff_address,
                scheduled_date,
                scheduled_time,
                passenger_name,
                status
            FROM charters
            WHERE assigned_employee_id = %s
              AND DATE(scheduled_date) = CURRENT_DATE
            ORDER BY scheduled_time ASC
        """,
            (employee_id,),
        )

        trips = []
        for row in cur.fetchall():
            trips.append(
                {
                    "charter_id": row[0],
                    "reserve_number": row[1],
                    "pickup": row[2],
                    "dropoff": row[3],
                    "date": str(row[4]),
                    "time": str(row[5]),
                    "passenger": row[6],
                    "status": row[7],
                }
            )

        cur.close()
        conn.close()
        return trips
    except Exception as e:
        print(f"Error fetching trips: {e}")
        return []
