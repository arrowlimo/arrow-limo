"""Dashboard metrics endpoint - returns JSON with operational KPIs"""
from fastapi import APIRouter, Query
from datetime import datetime, timedelta
from ..db import cursor

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard_metrics(date_filter: str = Query("", description="Date filter: today, upcoming_week, this_month, this_year, future_all")):
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
            
            # Calculate date range based on filter
            if date_filter == "today":
                start_date = today
                end_date = today
            elif date_filter == "upcoming_week":
                start_date = today
                end_date = today + timedelta(days=7)
            elif date_filter == "this_month":
                start_date = today.replace(day=1)
                end_date = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
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
            query = """SELECT COUNT(*) FROM charters WHERE closed = FALSE AND cancelled = FALSE"""
            params = []
            if start_date and end_date:
                query += """ AND charter_date BETWEEN %s AND %s"""
                params = [start_date, end_date]
            cur.execute(query, params)
            open_charters = cur.fetchone()[0] or 0
            
            # Balance owing (sum of outstanding balances)
            query = """
                SELECT COALESCE(SUM(c.total_amount_due - COALESCE(p.total_paid, 0)), 0)
                FROM charters c
                LEFT JOIN (
                    SELECT reserve_number, COALESCE(SUM(amount), 0) as total_paid
                    FROM payments
                    GROUP BY reserve_number
                ) p ON c.reserve_number = p.reserve_number
                WHERE c.closed = FALSE AND c.cancelled = FALSE
            """
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
                        SELECT reserve_number, COALESCE(SUM(amount), 0) as total_paid
                        FROM payments
                        GROUP BY reserve_number
                    ) p ON c.reserve_number = p.reserve_number
                    WHERE c.closed = FALSE AND c.cancelled = FALSE
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
            cur.execute("""
                SELECT COUNT(*) FROM vehicles v
                WHERE v.status != 'retired'
                AND (
                    v.next_maintenance_date IS NOT NULL AND v.next_maintenance_date < CURRENT_DATE
                    OR v.last_inspection_date IS NULL
                    OR v.last_inspection_date < CURRENT_DATE - INTERVAL '6 months'
                )
            """)
            vehicle_warning = cur.fetchone()[0] or 0
            
            # Driver warnings (not certified, documents expiring, etc)
            cur.execute("""
                SELECT COUNT(*) FROM employees e
                WHERE e.employee_type = 'driver'
                AND e.status = 'active'
                AND (
                    e.driver_license_expiry IS NULL
                    OR e.driver_license_expiry < CURRENT_DATE + INTERVAL '30 days'
                    OR e.medical_certificate_expiry IS NULL
                    OR e.medical_certificate_expiry < CURRENT_DATE
                )
            """)
            driver_warning = cur.fetchone()[0] or 0
            
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
            "error": str(e)
        }
