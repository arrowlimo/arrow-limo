from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/chauffeur", tags=["chauffeur_self_service"])
TRIP_UPDATE_COLUMNS = {
    "driver_notes": "driver_notes",
    "vehicle_notes": "vehicle_notes",
    "odometer_start": "odometer_start",
    "odometer_end": "odometer_end",
    "fuel_added_liters": "fuel_added_liters",
    "actual_hours": "actual_hours",
    "status": "status",
}


class DriverTripUpdate(BaseModel):
    driver_notes: str | None = Field(default=None, max_length=4000)
    vehicle_notes: str | None = Field(default=None, max_length=4000)
    odometer_start: Decimal | None = Field(default=None, ge=0)
    odometer_end: Decimal | None = Field(default=None, ge=0)
    fuel_added_liters: Decimal | None = Field(default=None, ge=0)
    actual_hours: Decimal | None = Field(default=None, ge=0, le=24)
    bus_driving_hours: Decimal | None = Field(default=None, ge=0, le=24)
    break_minutes: int | None = Field(default=None, ge=0, le=1440)
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


def _hours(value) -> float | None:
    if value is None or value == "":
        return None
    return round(float(value), 2)


def _as_datetime(day: date, value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "hour"):
        return datetime.combine(day, value)
    return None


def _daily_hos_status(
    *,
    day: date,
    on_duty: float | None,
    driving: float | None,
    off_duty: float | None,
    worked: bool,
    bus_worked: bool,
    capacity_missing: bool,
    has_hos_record: bool,
    rest_before: float | None,
    shift_elapsed: float | None,
) -> tuple[str, list[str]]:
    alerts = []
    warnings = []
    if worked and not has_hos_record:
        alerts.append("Assigned charter exists but the HOS time record is missing.")
    if bus_worked and driving is None:
        alerts.append("D.A.B. hours are not recorded.")
    if capacity_missing:
        warnings.append(
            "Assigned vehicle capacity is missing; D.A.B. classification cannot be confirmed."
        )
    if on_duty is not None and off_duty is not None:
        total = round(on_duty + off_duty, 2)
        if abs(total - 24) > 0.01:
            alerts.append(f"On-duty and off-duty hours total {total:g}, not 24.")
    elif has_hos_record:
        alerts.append("On-duty or off-duty hours are incomplete.")
    if driving is not None and driving > 13:
        alerts.append("Driving exceeds Alberta's 13-hour limit.")
    if on_duty is not None and on_duty >= 15:
        warnings.append(
            "On-duty time reached Alberta's 15-hour driving cutoff; "
            "verify that no driving occurred after the cutoff."
        )
    if rest_before is not None and rest_before < 8:
        alerts.append(
            f"Only {rest_before:g} consecutive hours off before this shift; 8 are required."
        )
    if shift_elapsed is not None and shift_elapsed > 15:
        alerts.append(
            f"Shift elapsed time is {shift_elapsed:g} hours; the Alberta 160 km "
            "daily-log exemption requires release within 15 hours."
        )

    if alerts:
        return "red", alerts
    if day == date.today():
        warnings.append("Current-day totals are provisional until the day is complete.")
    if rest_before is not None and abs(rest_before - 8) <= 0.01:
        warnings.append("Minimum 8 consecutive hours off before this shift.")
    if bus_worked:
        warnings.append(
            "Confirm the required Alberta continuous-driving breaks from duty timestamps."
        )
    if warnings:
        return "yellow", warnings
    if not worked and not has_hos_record:
        return "green", ["No assigned work; 24 hours off duty."]
    return "green", ["Recorded daily totals have no Alberta HOS limit alerts."]


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


def _ensure_driver_charter_hos_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS driver_charter_hos (
                charter_id INTEGER PRIMARY KEY
                    REFERENCES charters(charter_id) ON DELETE CASCADE,
                employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
                bus_driving_hours NUMERIC(5, 2)
                    CHECK (bus_driving_hours BETWEEN 0 AND 24),
                break_minutes INTEGER CHECK (break_minutes BETWEEN 0 AND 1440),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_driver_charter_hos_employee
            ON driver_charter_hos (employee_id, charter_id)
            """
        )
    conn.commit()


def _get_owned_charter(cur, charter_id: int, employee_id: int):
    cur.execute(
        """
        SELECT
            c.charter_id, c.reserve_number, c.charter_date, c.pickup_time,
            c.dropoff_time, c.pickup_address, c.dropoff_address, c.status,
            COALESCE(c.driver_notes, ''), COALESCE(c.vehicle_notes, ''),
            c.odometer_start, c.odometer_end, c.total_kms,
            c.fuel_added_liters, c.actual_hours, c.completion_timestamp,
            COALESCE(c.float_received, 0), c.vehicle_id,
            COALESCE(v.vehicle_type, ''), v.passenger_capacity,
            h.bus_driving_hours, h.break_minutes
        FROM charters c
        LEFT JOIN vehicles v ON v.vehicle_id = c.vehicle_id
        LEFT JOIN driver_charter_hos h
          ON h.charter_id = c.charter_id AND h.employee_id = %s
        WHERE c.charter_id = %s
          AND (c.assigned_driver_id = %s OR c.employee_id = %s)
        LIMIT 1
        """,
        (employee_id, charter_id, employee_id, employee_id),
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
        "vehicle_type": row[18] or "",
        "passenger_capacity": int(row[19]) if row[19] is not None else None,
        "is_bus": row[19] is not None and int(row[19]) >= 11,
        "bus_driving_hours": float(row[20]) if row[20] is not None else None,
        "break_minutes": int(row[21]) if row[21] is not None else None,
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
                employee_category,
                hire_date,
                employment_status
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
            "hire_date": row[6].isoformat() if row[6] else None,
            "employment_status": row[7] or "",
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
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        cur = conn.cursor()
        current_month_start = date.today().replace(day=1)
        start_date = (current_month_start - timedelta(days=1)).replace(day=1)
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
            ORDER BY charter_date ASC, pickup_time ASC NULLS LAST
            LIMIT 251 OFFSET %s
            """,
            (employee_id, employee_id, start_date, offset),
        )
        rows = cur.fetchall()
        cur.close()
        has_more = len(rows) > 250
        rows = rows[:250]

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
            "count": len(items),
            "has_more": has_more,
            "next_offset": offset + len(items) if has_more else None,
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
        _ensure_driver_charter_hos_table(conn)
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
        _ensure_driver_charter_hos_table(conn)
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

            hos_updates = {
                field: updates.pop(field)
                for field in ("bus_driving_hours", "break_minutes")
                if field in updates
            }
            is_bus = existing[19] is not None and int(existing[19]) >= 11
            if not is_bus and (hos_updates.get("bus_driving_hours") or 0) > 0:
                raise HTTPException(
                    status_code=400,
                    detail="D.A.B. hours apply only to vehicles with capacity of 11 or more",
                )
            if not is_bus and "bus_driving_hours" in hos_updates:
                hos_updates["bus_driving_hours"] = Decimal("0")

            assignments = []
            values = []
            for field, value in updates.items():
                column = TRIP_UPDATE_COLUMNS.get(field)
                if not column:
                    raise HTTPException(status_code=400, detail="Unsupported driver field")
                assignments.append(f"{column} = %s")
                values.append(value)
            if assignments:
                if updates.get("status") == "completed":
                    assignments.append(
                        "completion_timestamp = COALESCE(completion_timestamp, NOW())"
                    )
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
            if hos_updates:
                update_clauses = [
                    f"{field} = EXCLUDED.{field}"
                    for field in ("bus_driving_hours", "break_minutes")
                    if field in hos_updates
                ]
                cur.execute(
                    f"""
                    INSERT INTO driver_charter_hos (
                        charter_id, employee_id, bus_driving_hours, break_minutes
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (charter_id) DO UPDATE SET
                        employee_id = EXCLUDED.employee_id,
                        {", ".join(update_clauses)},
                        updated_at = NOW()
                    """,
                    (
                        charter_id,
                        employee_id,
                        hos_updates.get("bus_driving_hours"),
                        hos_updates.get("break_minutes"),
                    ),
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
                    epm.employee_pay_id,
                    pp.fiscal_year,
                    EXTRACT(MONTH FROM pp.period_end_date)::integer,
                    pp.period_start_date,
                    pp.period_end_date,
                    pp.pay_date,
                    epm.total_hours_worked,
                    epm.overtime_hours,
                    epm.gross_pay,
                    epm.total_deductions,
                    epm.net_pay,
                    epm.notes,
                    COALESCE(epm.updated_at, epm.created_at)
                FROM employee_pay_master epm
                JOIN pay_periods pp ON pp.pay_period_id = epm.pay_period_id
                WHERE epm.employee_id = %s AND pp.fiscal_year = %s
                ORDER BY pp.period_number ASC, pp.period_start_date ASC
                """,
                (employee_id, year),
            )
            rows = cur.fetchall()

        items = [
            {
                "statement_id": row[0],
                "year": row[1],
                "month": row[2],
                "period_start": row[3].isoformat() if row[3] else None,
                "period_end": row[4].isoformat() if row[4] else None,
                "pay_date": row[5].isoformat() if row[5] else None,
                "total_hours": float(row[6]) if row[6] is not None else None,
                "overtime_hours": float(row[7]) if row[7] is not None else None,
                "gross_pay": float(row[8]) if row[8] is not None else None,
                "deductions": float(row[9]) if row[9] is not None else None,
                "net_pay": float(row[10]) if row[10] is not None else None,
                "notes": row[11] or "",
                "saved_at": row[12].isoformat() if row[12] else None,
            }
            for row in rows
        ]
        return {"year": year, "items": items}
    finally:
        return_connection(conn)


@router.get("/me/t4s")
def get_my_t4s(current_user: dict = Depends(get_current_user)):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    to_regclass('public.employee_t4_records') IS NOT NULL,
                    to_regclass('public.t4_entries') IS NOT NULL
                """
            )
            current_exists, legacy_exists = cur.fetchone()
            if not current_exists and not legacy_exists:
                raise HTTPException(status_code=503, detail="Saved T4 records are unavailable")

            rows_by_year = {}
            if current_exists:
                cur.execute(
                    """
                    SELECT
                        tax_year,
                        box_14_employment_income,
                        box_16_cpp_contributions,
                        box_18_ei_premiums,
                        box_22_income_tax,
                        box_24_ei_insurable_earnings,
                        box_26_cpp_pensionable_earnings,
                        box_44_union_dues,
                        box_46_charitable_donations,
                        box_52_pension_adjustment,
                        notes
                    FROM employee_t4_records
                    WHERE employee_id = %s
                    ORDER BY tax_year DESC
                    """,
                    (employee_id,),
                )
                rows_by_year.update({row[0]: row for row in cur.fetchall()})
            if legacy_exists:
                cur.execute(
                    """
                    SELECT
                        tax_year,
                        t4_box_14,
                        t4_box_16,
                        t4_box_18,
                        t4_box_22,
                        t4_box_24,
                        t4_box_26,
                        t4_box_44,
                        t4_box_46,
                        t4_box_52,
                        notes
                    FROM t4_entries
                    WHERE employee_id = %s
                    ORDER BY tax_year DESC
                    """,
                    (employee_id,),
                )
                for row in cur.fetchall():
                    rows_by_year.setdefault(row[0], row)
            rows = [rows_by_year[year] for year in sorted(rows_by_year, reverse=True)]

        items = [
            {
                "tax_year": row[0],
                "box_14": float(row[1]) if row[1] is not None else None,
                "box_16": float(row[2]) if row[2] is not None else None,
                "box_18": float(row[3]) if row[3] is not None else None,
                "box_22": float(row[4]) if row[4] is not None else None,
                "box_24": float(row[5]) if row[5] is not None else None,
                "box_26": float(row[6]) if row[6] is not None else None,
                "box_44": float(row[7]) if row[7] is not None else None,
                "box_46": float(row[8]) if row[8] is not None else None,
                "box_52": float(row[9]) if row[9] is not None else None,
                "notes": row[10] or "",
            }
            for row in rows
        ]
        return {"items": items}
    finally:
        return_connection(conn)


@router.get("/me/hos")
def get_my_hos(
    current_user: dict = Depends(get_current_user),
):
    employee_id = _employee_id_from_user(current_user)
    conn = get_connection()
    try:
        days = 14
        start_date = date.today() - timedelta(days=days - 1)
        query_start = start_date - timedelta(days=1)
        _ensure_driver_charter_hos_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'hos_log'
                """
            )
            columns = {row[0] for row in cur.fetchall()}
            if {"hos_date", "on_duty_hours", "off_duty_hours"} <= columns:
                on_duty_start = (
                    "MIN(on_duty_start)" if "on_duty_start" in columns else "NULL::timestamp"
                )
                off_duty_at = "MAX(off_duty_at)" if "off_duty_at" in columns else "NULL::timestamp"
                cur.execute(
                    f"""
                    SELECT
                        hos_date,
                        {on_duty_start},
                        {off_duty_at},
                        SUM(on_duty_hours),
                        NULL::numeric,
                        SUM(off_duty_hours),
                        NULL::numeric,
                        '[]'::jsonb,
                        NULL::boolean,
                        NULL::numeric,
                        NULL::boolean,
                        NULL::text
                    FROM hos_log
                    WHERE employee_id = %s
                      AND hos_date >= %s
                    GROUP BY hos_date
                    ORDER BY hos_date ASC
                    """,
                    (employee_id, query_start),
                )
            elif "log_date" in columns:
                workshift_start = (
                    "workshift_start" if "workshift_start" in columns else "NULL::timestamp"
                )
                workshift_end = "workshift_end" if "workshift_end" in columns else "NULL::timestamp"
                optional_hos_columns = {
                    "total_on_duty": "NULL::numeric",
                    "total_driving": "NULL::numeric",
                    "total_off_duty": "NULL::numeric",
                    "breaks": "NULL::numeric",
                    "duty_log": "'[]'::jsonb",
                    "deferral": "NULL::boolean",
                    "deferral_hours": "NULL::numeric",
                    "emergency": "NULL::boolean",
                    "emergency_reason": "NULL::text",
                }
                selected_hos_columns = [
                    name if name in columns else fallback
                    for name, fallback in optional_hos_columns.items()
                ]
                cur.execute(
                    f"""
                    SELECT
                        log_date,
                        {workshift_start},
                        {workshift_end},
                        {", ".join(selected_hos_columns)}
                    FROM hos_log
                    WHERE employee_id = %s
                      AND log_date >= %s
                    ORDER BY log_date ASC
                    """,
                    (employee_id, query_start),
                )
            else:
                raise HTTPException(status_code=503, detail="HOS records are unavailable")
            hos_rows = cur.fetchall()
            cur.execute(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('charters', 'vehicles')
                """
            )
            table_columns: dict[str, set[str]] = {"charters": set(), "vehicles": set()}
            for table_name, column_name in cur.fetchall():
                table_columns[table_name].add(column_name)
            charter_columns = table_columns["charters"]
            vehicle_columns = table_columns["vehicles"]
            charter_optional = {
                "actual_hours": "NULL::numeric",
                "workshift_start": "NULL::timestamp",
                "workshift_end": "NULL::timestamp",
                "passenger_count": "NULL::integer",
                "is_out_of_town": "FALSE",
            }
            charter_select = {
                name: f"c.{name}" if name in charter_columns else fallback
                for name, fallback in charter_optional.items()
            }
            vehicle_number = (
                "v.vehicle_number" if "vehicle_number" in vehicle_columns else "NULL::text"
            )
            if "vehicle_number" not in vehicle_columns and "vehicle" in charter_columns:
                vehicle_number = "c.vehicle::text"
            passenger_capacity = (
                "v.passenger_capacity"
                if "passenger_capacity" in vehicle_columns
                else "NULL::integer"
            )
            vehicle_type = (
                "COALESCE(v.vehicle_type, '')" if "vehicle_type" in vehicle_columns else "''::text"
            )
            not_cancelled = (
                "AND COALESCE(c.cancelled, FALSE) = FALSE" if "cancelled" in charter_columns else ""
            )
            cur.execute(
                f"""
                SELECT
                    c.charter_id,
                    c.reserve_number,
                    c.charter_date,
                    c.pickup_time,
                    c.dropoff_time,
                    {charter_select["actual_hours"]},
                    {charter_select["workshift_start"]},
                    {charter_select["workshift_end"]},
                    {charter_select["passenger_count"]},
                    {charter_select["is_out_of_town"]},
                    c.status,
                    {vehicle_number},
                    {passenger_capacity},
                    {vehicle_type},
                    h.bus_driving_hours,
                    h.break_minutes
                FROM charters c
                LEFT JOIN vehicles v ON v.vehicle_id = c.vehicle_id
                LEFT JOIN driver_charter_hos h
                  ON h.charter_id = c.charter_id AND h.employee_id = %s
                WHERE (c.assigned_driver_id = %s OR c.employee_id = %s)
                  AND c.charter_date BETWEEN %s AND %s
                  {not_cancelled}
                  AND LOWER(COALESCE(c.status, '')) NOT LIKE 'cancel%'
                ORDER BY c.charter_date ASC, c.pickup_time ASC NULLS LAST
                """,
                (employee_id, employee_id, employee_id, start_date, date.today()),
            )
            charter_rows = cur.fetchall()

        hos_by_date = {row[0]: row for row in hos_rows if row[0]}
        charters_by_date: dict[date, list[dict]] = {}
        for row in charter_rows:
            charter_day = row[2]
            if not charter_day:
                continue
            capacity = int(row[12]) if row[12] is not None else None
            passengers = int(row[8]) if row[8] is not None else None
            vehicle_type = row[13] or ""
            charter_start = _as_datetime(charter_day, row[6]) or _as_datetime(charter_day, row[3])
            charter_end = _as_datetime(charter_day, row[7]) or _as_datetime(charter_day, row[4])
            if charter_start and charter_end and charter_end <= charter_start:
                charter_end += timedelta(days=1)
            charters_by_date.setdefault(charter_day, []).append(
                {
                    "charter_id": row[0],
                    "reserve_number": row[1] or str(row[0]),
                    "pickup_time": str(row[3]) if row[3] is not None else None,
                    "dropoff_time": str(row[4]) if row[4] is not None else None,
                    "actual_hours": _hours(row[5]),
                    "workshift_start": charter_start.isoformat() if charter_start else None,
                    "workshift_end": charter_end.isoformat() if charter_end else None,
                    "passenger_count": passengers,
                    "vehicle_number": row[11] or "",
                    "vehicle_type": vehicle_type,
                    "passenger_capacity": capacity,
                    "is_bus": capacity is not None and capacity >= 11,
                    "is_out_of_town": bool(row[9]),
                    "status": row[10] or "",
                    "bus_driving_hours": _hours(row[14]),
                    "break_minutes": int(row[15]) if row[15] is not None else None,
                }
            )

        entries = []
        previous_shift_end = None
        prior_row = hos_by_date.get(query_start)
        if prior_row:
            previous_shift_end = _as_datetime(query_start, prior_row[2])
        for offset in range(days):
            day = start_date + timedelta(days=offset)
            row = hos_by_date.get(day)
            day_charters = charters_by_date.get(day, [])
            bus_worked = any(charter["is_bus"] for charter in day_charters)
            capacity_missing = any(
                charter["passenger_capacity"] is None for charter in day_charters
            )
            bus_charters = [charter for charter in day_charters if charter["is_bus"]]
            bus_hours = [charter["bus_driving_hours"] for charter in bus_charters]
            has_hos_record = row is not None
            on_duty = _hours(row[3]) if row else 0.0 if not day_charters else None
            driving = (
                round(sum(bus_hours), 2)
                if not capacity_missing
                and bus_hours
                and all(value is not None for value in bus_hours)
                else None
                if bus_worked or capacity_missing
                else 0.0
            )
            off_duty = _hours(row[5]) if row else 24.0 if not day_charters else None
            shift_start = _as_datetime(day, row[1]) if row else None
            shift_end = _as_datetime(day, row[2]) if row else None
            if shift_start and shift_end and shift_end <= shift_start:
                shift_end += timedelta(days=1)
            rest_before = None
            shift_elapsed = None
            if shift_start and previous_shift_end:
                rest_before = round(
                    max(0, (shift_start - previous_shift_end).total_seconds() / 3600), 2
                )
            if shift_start and shift_end:
                shift_elapsed = round((shift_end - shift_start).total_seconds() / 3600, 2)
            status, alerts = _daily_hos_status(
                day=day,
                on_duty=on_duty,
                driving=driving,
                off_duty=off_duty,
                worked=bool(day_charters),
                bus_worked=bus_worked,
                capacity_missing=capacity_missing,
                has_hos_record=has_hos_record,
                rest_before=rest_before,
                shift_elapsed=shift_elapsed,
            )
            entries.append(
                {
                    "date": day.isoformat(),
                    "workshift_start": shift_start.isoformat() if shift_start else None,
                    "workshift_end": shift_end.isoformat() if shift_end else None,
                    "total_on_duty": on_duty,
                    "total_driving": driving,
                    "total_off_duty": off_duty,
                    "total_hours": (
                        round(on_duty + off_duty, 2)
                        if on_duty is not None and off_duty is not None
                        else None
                    ),
                    "breaks": _hours(row[6]) if row else None,
                    "rest_before_shift": rest_before,
                    "shift_elapsed": shift_elapsed,
                    "status": status,
                    "alerts": alerts,
                    "charters": day_charters,
                    "has_hos_record": has_hos_record,
                    "duty_log": row[7] if row and isinstance(row[7], list) else [],
                }
            )
            if shift_end:
                previous_shift_end = shift_end

        return {
            "employee_id": employee_id,
            "days": days,
            "source": "hos_log",
            "jurisdiction": "Alberta provincial",
            "daily_log_exemption": "160 km radius",
            "rules": {
                "driving_limit_hours": 13,
                "on_duty_driving_cutoff_hours": 15,
                "minimum_consecutive_off_duty_hours": 8,
                "break_rule": (
                    "10 minutes after up to 4 continuous driving hours; "
                    "30 minutes after more than 4 and up to 6 continuous driving hours."
                ),
                "record_retention_months": 6,
            },
            "items": list(reversed(entries)),
        }
    finally:
        return_connection(conn)
