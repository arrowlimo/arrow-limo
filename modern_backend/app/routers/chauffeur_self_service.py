from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/chauffeur", tags=["chauffeur_self_service"])


class DriverTripUpdate(BaseModel):
    driver_notes: str | None = Field(default=None, max_length=4000)
    vehicle_notes: str | None = Field(default=None, max_length=4000)
    odometer_start: Decimal | None = Field(default=None, ge=0)
    odometer_end: Decimal | None = Field(default=None, ge=0)
    fuel_added_liters: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0, le=24)
    status: Literal["in_progress", "completed"] | None = None


class DriverReceiptCreate(BaseModel):
    receipt_date: date
    vendor_name: str = Field(min_length=1, max_length=255)
    gross_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    charter_id: int | None = None
    paid_from_float: bool = False


class DriverFloatReturnCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    charter_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


def _employee_id_from_user(user: dict) -> int:
    employee_id = user.get("employee_id")
    if employee_id is None:
        raise HTTPException(status_code=403, detail="Employee context required")
    try:
        return int(employee_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Invalid employee context") from exc


def _ensure_driver_portal_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS driver_receipt_submissions (
                receipt_id INTEGER PRIMARY KEY REFERENCES receipts(receipt_id) ON DELETE CASCADE,
                employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
                paid_from_float BOOLEAN NOT NULL DEFAULT FALSE,
                submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_driver_receipt_submissions_employee
            ON driver_receipt_submissions (employee_id, submitted_at DESC)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS driver_float_returns (
                return_id BIGSERIAL PRIMARY KEY,
                employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
                charter_id INTEGER NULL REFERENCES charters(charter_id),
                amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
                notes TEXT NULL,
                submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_driver_float_returns_employee
            ON driver_float_returns (employee_id, submitted_at DESC)
            """
        )
    conn.commit()


def _get_owned_charter(cur, charter_id: int, employee_id: int):
    cur.execute(
        """
        SELECT
            charter_id, reserve_number, charter_date, pickup_time, dropoff_time,
            pickup_address, dropoff_address, status, COALESCE(driver_notes, ''),
            COALESCE(vehicle_notes, ''), odometer_start, odometer_end, total_kms,
            fuel_added_liters, actual_hours, completion_timestamp,
            COALESCE(float_received, 0), vehicle_id
        FROM charters
        WHERE charter_id = %s
          AND (assigned_driver_id = %s OR employee_id = %s)
        LIMIT 1
        """,
        (charter_id, employee_id, employee_id),
    )
    return cur.fetchone()


def _trip_payload(row) -> dict:
    return {
        "charter_id": row[0],
        "reserve_number": row[1],
        "date": row[2].isoformat() if row[2] else None,
        "pickup_time": str(row[3]) if row[3] is not None else None,
        "dropoff_time": str(row[4]) if row[4] is not None else None,
        "pickup_address": row[5] or "",
        "dropoff_address": row[6] or "",
        "status": row[7] or "",
        "driver_notes": row[8] or "",
        "vehicle_notes": row[9] or "",
        "odometer_start": float(row[10]) if row[10] is not None else None,
        "odometer_end": float(row[11]) if row[11] is not None else None,
        "total_kms": float(row[12]) if row[12] is not None else None,
        "fuel_added_liters": float(row[13]) if row[13] is not None else None,
        "actual_hours": float(row[14]) if row[14] is not None else None,
        "completion_timestamp": row[15].isoformat() if row[15] else None,
        "float_received": float(row[16] or 0),
        "vehicle_id": row[17],
    }


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


@router.get("/me/trips/{charter_id}")
def get_my_trip(
    charter_id: int,
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            row = _get_owned_charter(cur, charter_id, employee_id)
        if not row:
            raise HTTPException(status_code=404, detail="Trip not found")
        return _trip_payload(row)
    finally:
        return_connection(conn)


@router.patch("/me/trips/{charter_id}")
def update_my_trip(
    charter_id: int,
    payload: DriverTripUpdate,
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No driver fields supplied")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            existing = _get_owned_charter(cur, charter_id, employee_id)
            if not existing:
                raise HTTPException(status_code=404, detail="Trip not found")
            odometer_start = updates.get("odometer_start", existing[10])
            odometer_end = updates.get("odometer_end", existing[11])
            if (
                odometer_start is not None
                and odometer_end is not None
                and odometer_end < odometer_start
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Ending odometer cannot be lower than starting odometer",
                )

            assignments = []
            values = []
            for field, value in updates.items():
                assignments.append(f"{field} = %s")
                values.append(value)
            if updates.get("status") == "completed":
                assignments.append("completion_timestamp = COALESCE(completion_timestamp, NOW())")
            assignments.append("updated_at = NOW()")
            values.extend([charter_id, employee_id, employee_id])
            cur.execute(
                f"""
                UPDATE charters
                SET {", ".join(assignments)}
                WHERE charter_id = %s
                  AND (assigned_driver_id = %s OR employee_id = %s)
                """,
                values,
            )
            row = _get_owned_charter(cur, charter_id, employee_id)
        conn.commit()
        return _trip_payload(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.get("/me/receipts")
def get_my_receipts(current_user: dict = Depends(get_current_user)):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        _ensure_driver_portal_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
                    r.category, r.description, r.charter_id,
                    c.reserve_number, d.paid_from_float, d.submitted_at
                FROM driver_receipt_submissions d
                JOIN receipts r ON r.receipt_id = d.receipt_id
                LEFT JOIN charters c ON c.charter_id = r.charter_id
                WHERE d.employee_id = %s
                ORDER BY r.receipt_date DESC, r.receipt_id DESC
                """,
                (employee_id,),
            )
            rows = cur.fetchall()
        return {
            "items": [
                {
                    "receipt_id": row[0],
                    "receipt_date": row[1].isoformat(),
                    "vendor_name": row[2],
                    "gross_amount": float(row[3] or 0),
                    "category": row[4] or "",
                    "description": row[5] or "",
                    "charter_id": row[6],
                    "reserve_number": row[7],
                    "paid_from_float": bool(row[8]),
                    "submitted_at": row[9].isoformat() if row[9] else None,
                }
                for row in rows
            ]
        }
    finally:
        return_connection(conn)


@router.post("/me/receipts", status_code=201)
def create_my_receipt(
    payload: DriverReceiptCreate,
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        _ensure_driver_portal_tables(conn)
        with conn.cursor() as cur:
            reserve_number = None
            if payload.charter_id is not None:
                charter = _get_owned_charter(cur, payload.charter_id, employee_id)
                if not charter:
                    raise HTTPException(status_code=404, detail="Trip not found")
                reserve_number = charter[1]

            gst = (payload.gross_amount * Decimal("0.05") / Decimal("1.05")).quantize(
                Decimal("0.01")
            )
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor, gross_amount,
                    gst_amount, gst_code, category, description, charter_id,
                    employee_id, reserve_number
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING receipt_id
                """,
                (
                    payload.receipt_date,
                    payload.vendor_name.strip(),
                    payload.vendor_name.strip().upper(),
                    payload.gross_amount,
                    gst,
                    "GST",
                    payload.category,
                    payload.description,
                    payload.charter_id,
                    employee_id,
                    reserve_number,
                ),
            )
            receipt_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO driver_receipt_submissions (
                    receipt_id, employee_id, paid_from_float
                )
                VALUES (%s, %s, %s)
                """,
                (receipt_id, employee_id, payload.paid_from_float),
            )
        conn.commit()
        return {"receipt_id": receipt_id, "status": "submitted"}
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.get("/me/float")
def get_my_float(current_user: dict = Depends(get_current_user)):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        _ensure_driver_portal_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(float_received), 0)
                FROM charters
                WHERE assigned_driver_id = %s OR employee_id = %s
                """,
                (employee_id, employee_id),
            )
            issued = Decimal(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT COALESCE(SUM(r.gross_amount), 0)
                FROM driver_receipt_submissions d
                JOIN receipts r ON r.receipt_id = d.receipt_id
                WHERE d.employee_id = %s AND d.paid_from_float = TRUE
                """,
                (employee_id,),
            )
            spent = Decimal(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT COALESCE(SUM(r.gross_amount), 0)
                FROM driver_receipt_submissions d
                JOIN receipts r ON r.receipt_id = d.receipt_id
                WHERE d.employee_id = %s AND d.paid_from_float = FALSE
                """,
                (employee_id,),
            )
            driver_paid = Decimal(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM driver_float_returns
                WHERE employee_id = %s
                """,
                (employee_id,),
            )
            returned = Decimal(cur.fetchone()[0] or 0)

        remaining = max(issued - spent - returned, Decimal("0"))
        return {
            "issued": float(issued),
            "receipts": float(spent),
            "driver_paid": float(driver_paid),
            "returned": float(returned),
            "remaining": float(remaining),
            "reimbursement_due": float(driver_paid),
            "settled": remaining == 0,
        }
    finally:
        return_connection(conn)


@router.post("/me/float/returns", status_code=201)
def record_my_float_return(
    payload: DriverFloatReturnCreate,
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        _ensure_driver_portal_tables(conn)
        with conn.cursor() as cur:
            if payload.charter_id is not None:
                charter = _get_owned_charter(cur, payload.charter_id, employee_id)
                if not charter:
                    raise HTTPException(status_code=404, detail="Trip not found")
            cur.execute(
                """
                SELECT
                    COALESCE((
                        SELECT SUM(float_received)
                        FROM charters
                        WHERE assigned_driver_id = %s OR employee_id = %s
                    ), 0)
                    - COALESCE((
                        SELECT SUM(r.gross_amount)
                        FROM driver_receipt_submissions d
                        JOIN receipts r ON r.receipt_id = d.receipt_id
                        WHERE d.employee_id = %s AND d.paid_from_float = TRUE
                    ), 0)
                    - COALESCE((
                        SELECT SUM(amount)
                        FROM driver_float_returns
                        WHERE employee_id = %s
                    ), 0)
                """,
                (employee_id, employee_id, employee_id, employee_id),
            )
            remaining = Decimal(cur.fetchone()[0] or 0)
            if payload.amount > max(remaining, Decimal("0")):
                raise HTTPException(
                    status_code=400,
                    detail="Turn-in amount exceeds the float still held",
                )
            cur.execute(
                """
                INSERT INTO driver_float_returns (
                    employee_id, charter_id, amount, notes
                )
                VALUES (%s, %s, %s, %s)
                RETURNING return_id, submitted_at
                """,
                (employee_id, payload.charter_id, payload.amount, payload.notes),
            )
            row = cur.fetchone()
        conn.commit()
        return {
            "return_id": row[0],
            "submitted_at": row[1].isoformat(),
            "status": "submitted",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        return_connection(conn)


@router.get("/me/pay-statements")
def get_my_pay_statements(
    year: int = Query(default_factory=lambda: datetime.now().year, ge=2000, le=2100),
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, year, pay_period, regular_hours, hourly_rate, ot_hours,
                    ot_rate, base_salary, bonus, gratuity, other_benefits,
                    cpp, ei, income_tax, notes, COALESCE(updated_at, created_at)
                FROM payroll_entries
                WHERE employee_id = %s AND year = %s
                ORDER BY COALESCE(updated_at, created_at) DESC NULLS LAST, id DESC
                """,
                (employee_id, year),
            )
            rows = cur.fetchall()

        items = []
        for row in rows:
            gross = sum(
                Decimal(row[index] or 0)
                for index in (7, 8, 9, 10)
            ) + Decimal(row[3] or 0) * Decimal(row[4] or 0) + Decimal(
                row[5] or 0
            ) * Decimal(row[6] or 0)
            deductions = sum(Decimal(row[index] or 0) for index in (11, 12, 13))
            items.append(
                {
                    "statement_id": row[0],
                    "year": row[1],
                    "pay_period": row[2],
                    "regular_hours": float(row[3] or 0),
                    "overtime_hours": float(row[5] or 0),
                    "gross_pay": float(gross),
                    "deductions": float(deductions),
                    "net_pay": float(gross - deductions),
                    "notes": row[14] or "",
                    "issued_at": row[15].isoformat() if row[15] else None,
                }
            )
        return {"year": year, "items": items}
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
