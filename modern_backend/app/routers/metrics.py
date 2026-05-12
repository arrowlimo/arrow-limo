"""Dashboard metrics endpoint - returns JSON with operational KPIs"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from ..db import cursor

router = APIRouter(prefix="/api", tags=["dashboard"])


def _existing_columns(cur, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cur.fetchall()}


@router.get("/dashboard")
def get_dashboard_metrics(
    date_filter: str = Query(
        "",
        description=(
            "Date filter: today, upcoming_week, "
            "this_month, this_year, future_all"
        ),
    )
):
    """
    Return operational dashboard metrics as JSON
    - open_quotes: Count of quotations not converted to charters
    - open_charters: Count of charters not yet closed/completed
    - balance_owing: Sum of outstanding balances
    - balance_owing_count: Count of charters with balance > 0
    - vehicle_warning: Count of vehicles needing maintenance
    - driver_warning: Count of drivers with active issues
    """
    try:
        with cursor() as cur:
            today = datetime.now().date()
            charter_cols = _existing_columns(cur, "charters")
            vehicle_cols = _existing_columns(cur, "vehicles")
            employee_cols = _existing_columns(cur, "employees")

            if "closed" in charter_cols:
                open_expr = "COALESCE(c.closed, FALSE) = FALSE"
            elif "locked" in charter_cols:
                open_expr = "COALESCE(c.locked, FALSE) = FALSE"
            else:
                open_expr = "TRUE"

            if "cancelled" in charter_cols:
                not_cancelled_expr = "COALESCE(c.cancelled, FALSE) = FALSE"
            elif "status" in charter_cols:
                not_cancelled_expr = "LOWER(COALESCE(c.status, '')) != 'cancelled'"
            else:
                not_cancelled_expr = "TRUE"

            # Calculate date range based on filter
            if date_filter == "today":
                start_date = today
                end_date = today
            elif date_filter == "upcoming_week":
                start_date = today
                end_date = today + timedelta(days=7)
            elif date_filter == "this_month":
                start_date = today.replace(day=1)
                end_date = (today.replace(day=1) + timedelta(days=32)).replace(
                    day=1
                ) - timedelta(days=1)
            elif date_filter == "this_year":
                start_date = today.replace(month=1, day=1)
                end_date = today.replace(month=12, day=31)
            elif date_filter == "future_all":
                start_date = today
                end_date = today.replace(year=today.year + 10)
            else:
                start_date = None
                end_date = None

            # Open quotes (quotations not yet booked)
            cur.execute("""
                SELECT COUNT(*) FROM quotations 
                WHERE status = 'open' OR status IS NULL
            """)
            open_quotes = cur.fetchone()[0] or 0

            # Open charters (not closed)
            query = (
                "SELECT COUNT(*) FROM charters "
                f"WHERE {open_expr} AND {not_cancelled_expr}"
            )
            params = []
            if start_date and end_date:
                query += """ AND charter_date BETWEEN %s AND %s"""
                params = [start_date, end_date]
            cur.execute(query, params)
            open_charters = cur.fetchone()[0] or 0

            # Balance owing (sum of outstanding balances)
            query = """
                SELECT COALESCE(SUM(c.total_amount_due - COALESCE(p.total_paid,
                0)), 0)
                FROM charters c
                LEFT JOIN (
                    SELECT reserve_number, COALESCE(SUM(amount),
                    0) as total_paid
                    FROM payments
                    GROUP BY reserve_number
                ) p ON c.reserve_number = p.reserve_number
                WHERE
            """
            query += f" {open_expr} AND {not_cancelled_expr}"
            params = []
            if start_date and end_date:
                query += """ AND c.charter_date BETWEEN %s AND %s"""
                params = [start_date, end_date]
            cur.execute(query, params)
            balance_owing_total = float(cur.fetchone()[0] or 0.0)

            # Count of charters with balance > 0
            query = """
                SELECT COUNT(*)
                FROM (
                    SELECT c.charter_id
                    FROM charters c
                    LEFT JOIN (
                        SELECT reserve_number, COALESCE(SUM(amount),
                        0) as total_paid
                        FROM payments
                        GROUP BY reserve_number
                    ) p ON c.reserve_number = p.reserve_number
                        WHERE
            """
            query += f" {open_expr} AND {not_cancelled_expr}"
            query += """
                AND (c.total_amount_due - COALESCE(p.total_paid, 0)) > 0
            """
            if start_date and end_date:
                query += """ AND c.charter_date BETWEEN %s AND %s"""
            query += """ ) sub"""
            params = []
            if start_date and end_date:
                params = [start_date, end_date]
            cur.execute(query, params)
            balance_owing_count = cur.fetchone()[0] or 0

            # Vehicle warnings (maintenance overdue or no recent inspection)
            vehicle_predicates: list[str] = []
            if "status" in vehicle_cols:
                vehicle_predicates.append("COALESCE(v.status, '') != 'retired'")
            if "next_maintenance_date" in vehicle_cols:
                vehicle_predicates.append(
                    "(v.next_maintenance_date IS NOT NULL AND v.next_maintenance_date < CURRENT_DATE)"
                )
            if "last_inspection_date" in vehicle_cols:
                vehicle_predicates.append(
                    "(v.last_inspection_date IS NULL OR v.last_inspection_date < CURRENT_DATE - INTERVAL '6 months')"
                )

            if vehicle_predicates:
                base_filter = "TRUE"
                if "status" in vehicle_cols:
                    base_filter = "COALESCE(v.status, '') != 'retired'"
                warning_filter = " OR ".join(
                    p for p in vehicle_predicates if p != base_filter
                )
                if warning_filter:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM vehicles v
                        WHERE {base_filter} AND ({warning_filter})
                        """
                    )
                    vehicle_warning = cur.fetchone()[0] or 0
                else:
                    vehicle_warning = 0
            else:
                vehicle_warning = 0

            # Driver warnings (not certified, documents expiring, etc)
            employee_base: list[str] = []
            if "employee_type" in employee_cols:
                employee_base.append("LOWER(COALESCE(e.employee_type, '')) = 'driver'")
            if "status" in employee_cols:
                employee_base.append("LOWER(COALESCE(e.status, 'active')) = 'active'")
            base_where = " AND ".join(employee_base) if employee_base else "TRUE"

            driver_predicates: list[str] = []
            if "driver_license_expiry" in employee_cols:
                driver_predicates.append(
                    "(e.driver_license_expiry IS NULL OR e.driver_license_expiry < CURRENT_DATE + INTERVAL '30 days')"
                )
            if "medical_certificate_expiry" in employee_cols:
                driver_predicates.append(
                    "(e.medical_certificate_expiry IS NULL OR e.medical_certificate_expiry < CURRENT_DATE)"
                )

            if driver_predicates:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM employees e
                    WHERE {base_where} AND ({' OR '.join(driver_predicates)})
                    """
                )
                driver_warning = cur.fetchone()[0] or 0
            else:
                driver_warning = 0

            return {
                "open_quotes": open_quotes,
                "open_charters": open_charters,
                "balance_owing_total": balance_owing_total,
                "balance_owing_count": balance_owing_count,
                "vehicle_warning": vehicle_warning,
                "driver_warning": driver_warning,
            }
    except Exception as e:
        print(f"Dashboard metrics error: {e}")
        return {
            "open_quotes": 0,
            "open_charters": 0,
            "balance_owing_total": 0.0,
            "balance_owing_count": 0,
            "vehicle_warning": 0,
            "driver_warning": 0,
            "error": str(e),
        }
