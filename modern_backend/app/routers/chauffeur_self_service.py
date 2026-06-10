from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import get_current_user
from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/chauffeur", tags=["chauffeur_self_service"])


def _employee_id_from_user(user: dict) -> int:
    employee_id = user.get("employee_id")
    if employee_id is None:
        raise HTTPException(status_code=403, detail="Employee context required")
    try:
        return int(employee_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Invalid employee context") from exc


@router.get("/me/profile")
def get_my_profile(current_user: dict = Depends(get_current_user)):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                employee_id,
                first_name,
                last_name,
                email,
                phone,
                employee_category
            FROM employees
            WHERE employee_id = %s
            LIMIT 1
            """,
            (employee_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            raise HTTPException(status_code=404, detail="Employee profile not found")

        return {
            "employee_id": row[0],
            "first_name": row[1] or "",
            "last_name": row[2] or "",
            "name": f"{row[1] or ''} {row[2] or ''}".strip(),
            "email": row[3] or "",
            "phone": row[4] or "",
            "employee_type": row[5] or "",
        }
    finally:
        return_connection(conn)


@router.get("/me/trips")
def get_my_trips(
    days: int = Query(14, ge=1, le=90),
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        cur = conn.cursor()
        start_date = date.today() - timedelta(days=days)
        cur.execute(
            """
            SELECT
                charter_id,
                reserve_number,
                charter_date,
                pickup_time,
                dropoff_time,
                pickup_address,
                dropoff_address,
                status,
                COALESCE(driver_notes, '') AS driver_notes
            FROM charters
            WHERE (assigned_driver_id = %s OR employee_id = %s)
              AND charter_date >= %s
            ORDER BY charter_date DESC, pickup_time DESC NULLS LAST
            LIMIT 500
            """,
            (employee_id, employee_id, start_date),
        )
        rows = cur.fetchall()
        cur.close()

        trips = []
        for row in rows:
            trips.append(
                {
                    "charter_id": row[0],
                    "reserve_number": row[1],
                    "charter_date": row[2].isoformat() if row[2] else None,
                    "pickup_time": str(row[3]) if row[3] is not None else None,
                    "dropoff_time": str(row[4]) if row[4] is not None else None,
                    "pickup_address": row[5] or "",
                    "dropoff_address": row[6] or "",
                    "status": row[7] or "",
                    "driver_notes": row[8] or "",
                }
            )

        return {
            "employee_id": employee_id,
            "days": days,
            "count": len(trips),
            "items": trips,
        }
    finally:
        return_connection(conn)


@router.get("/me/calendar")
def get_my_calendar(
    days: int = Query(30, ge=1, le=120),
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        cur = conn.cursor()
        start_date = date.today()
        end_date = start_date + timedelta(days=days)
        cur.execute(
            """
            SELECT
                charter_id,
                reserve_number,
                charter_date,
                pickup_time,
                dropoff_time,
                pickup_address,
                dropoff_address,
                status
            FROM charters
            WHERE (assigned_driver_id = %s OR employee_id = %s)
              AND charter_date >= %s
              AND charter_date <= %s
            ORDER BY charter_date ASC, pickup_time ASC NULLS LAST
            LIMIT 500
            """,
            (employee_id, employee_id, start_date, end_date),
        )
        rows = cur.fetchall()
        cur.close()

        items = []
        for row in rows:
            items.append(
                {
                    "charter_id": row[0],
                    "reserve_number": row[1],
                    "date": row[2].isoformat() if row[2] else None,
                    "pickup_time": str(row[3]) if row[3] is not None else None,
                    "dropoff_time": str(row[4]) if row[4] is not None else None,
                    "pickup_address": row[5] or "",
                    "dropoff_address": row[6] or "",
                    "status": row[7] or "",
                }
            )

        return {
            "employee_id": employee_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "count": len(items),
            "items": items,
        }
    finally:
        return_connection(conn)


@router.get("/me/hos")
def get_my_hos(
    days: int = Query(14, ge=1, le=30),
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        cur = conn.cursor()
        start_date = date.today() - timedelta(days=days)

        # Prefer explicit hos_log records when present.
        try:
            cur.execute(
                """
                SELECT
                    log_date,
                    workshift_start,
                    workshift_end,
                    total_on_duty,
                    total_driving,
                    total_off_duty,
                    breaks,
                    duty_log,
                    COALESCE(deferral, false) AS deferral,
                    COALESCE(deferral_hours, 0) AS deferral_hours,
                    COALESCE(emergency, false) AS emergency,
                    emergency_reason
                FROM hos_log
                WHERE employee_id = %s
                  AND log_date >= %s
                ORDER BY log_date DESC
                """,
                (employee_id, start_date),
            )
            rows = cur.fetchall()
            if rows:
                entries = []
                for row in rows:
                    entries.append(
                        {
                            "date": row[0].isoformat() if row[0] else None,
                            "workshift_start": str(row[1]) if row[1] is not None else None,
                            "workshift_end": str(row[2]) if row[2] is not None else None,
                            "total_on_duty": str(row[3] or "0:00"),
                            "total_driving": str(row[4] or "0:00"),
                            "total_off_duty": str(row[5] or "0:00"),
                            "breaks": str(row[6] or "0:00"),
                            "duty_log": row[7] if isinstance(row[7], list) else [],
                            "deferral": bool(row[8]),
                            "deferral_hours": float(row[9] or 0),
                            "emergency": bool(row[10]),
                            "emergency_reason": row[11] or "",
                        }
                    )
                cur.close()
                return {
                    "employee_id": employee_id,
                    "days": days,
                    "source": "hos_log",
                    "items": entries,
                }
        except Exception:
            conn.rollback()

        # Fallback: derive a lightweight duty view from charters.
        cur.execute(
            """
            SELECT
                charter_date,
                MIN(pickup_time),
                MAX(dropoff_time),
                COUNT(*)
            FROM charters
            WHERE (assigned_driver_id = %s OR employee_id = %s)
              AND charter_date >= %s
            GROUP BY charter_date
            ORDER BY charter_date DESC
            """,
            (employee_id, employee_id, start_date),
        )
        rows = cur.fetchall()
        cur.close()

        entries = []
        for row in rows:
            trip_count = int(row[3] or 0)
            entries.append(
                {
                    "date": row[0].isoformat() if row[0] else None,
                    "workshift_start": str(row[1]) if row[1] is not None else None,
                    "workshift_end": str(row[2]) if row[2] is not None else None,
                    "total_on_duty": "",
                    "total_driving": "",
                    "total_off_duty": "",
                    "breaks": "",
                    "duty_log": [
                        {
                            "status": "Trips",
                            "start": str(row[1]) if row[1] is not None else "",
                            "end": str(row[2]) if row[2] is not None else "",
                            "duration": f"{trip_count} trip(s)",
                        }
                    ],
                    "deferral": False,
                    "deferral_hours": 0,
                    "emergency": False,
                    "emergency_reason": "",
                }
            )

        return {
            "employee_id": employee_id,
            "days": days,
            "source": "charters_fallback",
            "items": entries,
        }
    finally:
        return_connection(conn)


@router.get("/me/pay-summary")
def get_my_pay_summary(
    year: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                COALESCE(SUM(gross_pay), 0) AS gross_total,
                COUNT(*) AS pay_runs
            FROM driver_payroll
            WHERE employee_id = %s
              AND year = %s
            """,
            (employee_id, year),
        )
        payroll_row = cur.fetchone() or (0, 0)

        cur.execute(
            """
            SELECT
                pay_period,
                gross_pay,
                net_pay,
                payment_date
            FROM payroll_entries
            WHERE employee_id = %s
              AND year = %s
            ORDER BY payment_date DESC NULLS LAST, pay_period DESC
            LIMIT 50
            """,
            (employee_id, year),
        )
        recent_rows = cur.fetchall()
        cur.close()

        recent = []
        for row in recent_rows:
            recent.append(
                {
                    "pay_period": row[0],
                    "gross_pay": float(row[1] or 0),
                    "net_pay": float(row[2] or 0),
                    "payment_date": row[3].isoformat() if row[3] else None,
                }
            )

        return {
            "employee_id": employee_id,
            "year": year,
            "gross_total": float(payroll_row[0] or 0),
            "pay_runs": int(payroll_row[1] or 0),
            "recent_entries": recent,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.get("/me/paystub/{period}")
def get_my_paystub(
    period: str,
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        cur = conn.cursor()

        year, month = period.split("-") if "-" in period else (period[:4], period[4:6])
        cur.execute(
            """
            SELECT
                COALESCE(full_name, TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))),
                employee_id,
                COALESCE(t4_sin, sin)
            FROM employees
            WHERE employee_id = %s
            LIMIT 1
            """,
            (employee_id,),
        )
        emp = cur.fetchone()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        cur.execute(
            """
            SELECT
                COALESCE(regular_hours, 0),
                COALESCE(hourly_rate, 0),
                COALESCE(bonus, 0),
                COALESCE(gratuity, 0),
                COALESCE(cpp, 0),
                COALESCE(ei, 0),
                COALESCE(income_tax, 0)
            FROM payroll_entries
            WHERE employee_id = %s
              AND year = %s
              AND EXTRACT(MONTH FROM created_at) = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (employee_id, int(year), int(month)),
        )
        payroll = cur.fetchone()
        cur.close()

        if not payroll:
            raise HTTPException(status_code=404, detail="Payroll entry not found")

        hours = float(payroll[0] or 0)
        hourly_rate = float(payroll[1] or 0)
        bonus = float(payroll[2] or 0)
        gratuity = float(payroll[3] or 0)
        cpp = float(payroll[4] or 0)
        ei = float(payroll[5] or 0)
        income_tax = float(payroll[6] or 0)

        salary = hours * hourly_rate
        gross = salary + bonus + gratuity
        deductions = cpp + ei + income_tax
        net = gross - deductions

        return {
            "employeeId": employee_id,
            "employeeName": emp[0],
            "sin": emp[2],
            "period": f"{year}-{month:0>2}",
            "payDate": datetime.now().date().isoformat(),
            "hours": hours,
            "hourlyRate": hourly_rate,
            "bonus": bonus,
            "gratuity": gratuity,
            "gross": gross,
            "cpp": cpp,
            "ei": ei,
            "incomeTax": income_tax,
            "deductions": deductions,
            "netPay": net,
        }
    finally:
        return_connection(conn)
