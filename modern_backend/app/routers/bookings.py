import json
from contextlib import suppress
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Request

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import cursor
from ..utils.locked_charter import enforce_charter_not_locked

router = APIRouter(prefix="/api", tags=["bookings"])

RESERVE_SEQUENCE_MAX_AHEAD = 10000
SET_RESERVE_SEQUENCE_SQL = "SELECT setval('reserve_number_seq', %s, true)"


def _audit_actor(request: Request | None) -> AuditEventActor:
    if request is None:
        return AuditEventActor(actor_type="system", username="system")
    username = request.headers.get("X-User-Name") or request.headers.get("X-User")
    role = request.headers.get("X-User-Role")
    user_id = request.headers.get("X-User-Id")
    if not username:
        username = request.headers.get("X-Forwarded-User")
    return AuditEventActor(
        actor_type="user" if username else "service",
        user_id=user_id,
        username=username,
        role=role,
    )


def _fetch_charter_snapshot(cur, charter_id: int) -> dict[str, Any] | None:
    cur.execute("SELECT to_jsonb(c) FROM charters c WHERE c.charter_id = %s", (charter_id,))
    row = cur.fetchone()
    if not row:
        return None
    payload = row[0]
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    return json.loads(payload)


def _next_reserve_number(cur) -> str:
    """Generate the next reserve number and self-heal sequence drift."""
    cur.execute(
        "SELECT COALESCE(MAX(CAST(reserve_number AS BIGINT)), 0) FROM charters "
        "WHERE reserve_number ~ '^[0-9]+$'"
    )
    max_existing = int(cur.fetchone()[0] or 0)

    next_value = None
    try:
        cur.execute("SELECT nextval('reserve_number_seq')")
        seq_val = int(cur.fetchone()[0] or 0)

        # Guard against sequence corruption/jumps caused by bad manual values.
        if max_existing > 0 and seq_val > (max_existing + RESERVE_SEQUENCE_MAX_AHEAD):
            next_value = max_existing + 1
            cur.execute(SET_RESERVE_SEQUENCE_SQL, (next_value,))
        else:
            next_value = max(seq_val, max_existing + 1)
            cur.execute(SET_RESERVE_SEQUENCE_SQL, (next_value,))
    except Exception:
        next_value = max_existing + 1
        with suppress(Exception):
            cur.execute(SET_RESERVE_SEQUENCE_SQL, (next_value,))

    # Ensure uniqueness if manual corrections introduced collisions.
    for _ in range(50):
        reserve_number = f"{int(next_value):06d}"
        cur.execute("SELECT 1 FROM charters WHERE reserve_number = %s", (reserve_number,))
        if not cur.fetchone():
            return reserve_number
        next_value += 1
        with suppress(Exception):
            cur.execute(SET_RESERVE_SEQUENCE_SQL, (next_value,))

    return f"{int(next_value):06d}"


@router.get("/bookings")
def list_bookings(
    limit: Annotated[int, Query(ge=1, le=500, description="Max rows to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Rows to skip (for pagination)")] = 0,
):
    sql = """
        SELECT
            c.charter_id,
            c.charter_date,
            c.client_id,
            c.reserve_number,
            c.passenger_count,
            c.vehicle_id,
            COALESCE(v.vehicle_number, '') AS vehicle,
            COALESCE(v.make || ' ' || v.model, '') AS vehicle_description,
            COALESCE(e.first_name || ' ' || e.last_name, '') AS driver_name,
            c.nrd_amount AS retainer,
            c.nrd_received AS retainer_received,
            c.nrd_amount AS retainer_amount,
            c.odometer_start,
            c.odometer_end,
            0 AS fuel_added,
            c.vehicle_notes,
            c.client_notes AS notes,
            c.pickup_address,
            c.dropoff_address,
            c.pickup_time,
            c.status,
            c.locked AS closed,
            CASE WHEN c.status = 'cancelled'
                THEN true ELSE false END AS cancelled,
            COALESCE(c.charter_type, 'standard') AS charter_type,
            '{}' AS exchange_of_services_details,
            '4000' AS gl_revenue_code,
            '6100' AS gl_expense_code,
            cl.client_name,
            v.passenger_capacity AS vehicle_capacity,
            CASE
                WHEN COALESCE(c.cancelled, false) = true
                  OR LOWER(COALESCE(c.status, '')) = 'cancelled'
                THEN 0
                ELSE COALESCE(c.total_amount_due, 0)
            END AS total_amount_due,
            COALESCE(p.total_paid, 0) AS total_paid,
            CASE
                WHEN COALESCE(c.cancelled, false) = true
                  OR LOWER(COALESCE(c.status, '')) = 'cancelled'
                THEN 0
                ELSE GREATEST(
                    COALESCE(c.total_amount_due, 0) - COALESCE(p.total_paid, 0),
                    0
                )
            END AS balance,
            CASE
                WHEN c.locked = TRUE AND c.status != 'cancelled'
                    THEN 'Reconciled'
                WHEN c.status = 'cancelled' THEN 'Cancelled'
                WHEN c.locked = FALSE AND c.status != 'cancelled'
                    THEN 'Not Reconciled'
                ELSE 'Unknown'
            END AS reconciliation_status,
            COALESCE(nrr.nrr_amount, 0) AS nrr_amount,
            CASE WHEN nrr.nrr_amount > 0 THEN TRUE ELSE FALSE END AS
            nrr_received,
            EXISTS (
                SELECT 1
                FROM beverage_orders bo
                WHERE bo.reserve_number = c.reserve_number
                  AND bo.order_date >= date_trunc('week', CURRENT_DATE)
                  AND bo.order_date < date_trunc('week', CURRENT_DATE)
                      + interval '7 days') AS beverage_orders_this_week
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
        LEFT JOIN employees e ON c.employee_id = e.employee_id
        LEFT JOIN (
            SELECT reserve_number, COALESCE(SUM(amount), 0) AS total_paid
            FROM payments
            GROUP BY reserve_number) p ON p.reserve_number = c.reserve_number
        LEFT JOIN (
            SELECT reserve_number, COALESCE(SUM(amount), 0) AS nrr_amount
            FROM payments
            WHERE (
                payment_label IN (
                    'NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer')
                OR payment_key ILIKE '%%NRR%%'
                OR payment_key ILIKE '%%NRD%%')
            AND payment_label NOT IN (
                'Deposit', 'Security Deposit', 'Damage Deposit')
            GROUP BY reserve_number) nrr ON nrr.reserve_number =
            c.reserve_number
        ORDER BY c.charter_date DESC, c.charter_id DESC
        LIMIT %s OFFSET %s
        """
    with cursor() as cur:
        cur.execute(sql, (limit, offset))
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
    items: list[dict[str, Any]] = []
    for r in rows:
        rec = dict(zip(cols, r, strict=False))

        items.append(
            {
                "charter_id": rec.get("charter_id", ""),
                "charter_date": str(rec.get("charter_date", "")),
                "client_name": rec.get("client_name", "") or rec.get("client_id", "") or "",
                "client_id": rec.get("client_id", ""),
                "vehicle": rec.get("vehicle", ""),
                "vehicle_description": rec.get("vehicle_description", ""),
                "vehicle_id": rec.get("vehicle_id", ""),
                "driver_name": rec.get("driver_name", ""),
                "passenger_count": rec.get("passenger_count", 0),
                # Alias for frontend compatibility
                "passenger_load": rec.get("passenger_count", 0),
                "vehicle_capacity": rec.get("vehicle_capacity", 0),
                "retainer": float(rec.get("retainer", 0) or 0.0),
                "retainer_received": float(rec.get("retainer_received", 0) or 0.0),
                "retainer_amount": float(rec.get("retainer_amount", 0) or 0.0),
                "odometer_start": rec.get("odometer_start", ""),
                "odometer_end": rec.get("odometer_end", ""),
                "fuel_added": rec.get("fuel_added", ""),
                "vehicle_notes": rec.get("vehicle_notes", "") or rec.get("notes", ""),
                "itinerary": [],
                "reserve_number": rec.get("reserve_number", ""),
                "pickup_address": rec.get("pickup_address", ""),
                "pickup_time": (str(rec.get("pickup_time", "")) if rec.get("pickup_time") else ""),
                "dropoff_address": rec.get("dropoff_address", ""),
                "status": rec.get("status", ""),
                "closed": bool(rec.get("closed", False)),
                "cancelled": bool(rec.get("cancelled", False)),
                "charter_type": rec.get("charter_type", "standard"),
                "exchange_of_services_details": rec.get("exchange_of_services_details", {}),
                "gl_revenue_code": rec.get("gl_revenue_code", "4000"),
                "gl_expense_code": rec.get("gl_expense_code", "6100"),
                "reconciliation_status": rec.get("reconciliation_status", "Unknown"),
                "total_amount_due": float(rec.get("total_amount_due", 0) or 0.0),
                "paid_amount": float(rec.get("total_paid", 0) or 0.0),
                "total_paid": float(rec.get("total_paid", 0) or 0.0),
                "balance": float(rec.get("balance", 0) or 0.0),
                "nrr_amount": float(rec.get("nrr_amount", 0) or 0.0),
                "nrr_received": bool(rec.get("nrr_received", False)),
                "beverage_orders_this_week": bool(rec.get("beverage_orders_this_week", False)),
            }
        )
    return {"bookings": items}


@router.get("/bookings/{charter_id:int}")
def get_booking(charter_id: Annotated[int, Path()]):
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                c.charter_id,
                c.charter_date,
                c.client_id,
                c.reserve_number,
                c.passenger_count AS passenger_load,
                c.vehicle_id AS vehicle_booked_id,
                COALESCE(
                    v.description,
                    TRIM(COALESCE(v.make, '') || ' ' || COALESCE(v.model, '')),
                    ''
                ) AS vehicle_description,
                v.vehicle_type AS vehicle_type_requested,
                c.driver AS driver_name,
                c.driver,
                c.vehicle,
                NULL::numeric AS retainer,
                c.odometer_start,
                c.odometer_end,
                c.fuel_added,
                c.vehicle_notes,
                c.notes,
                c.pickup_address,
                c.dropoff_address,
                c.status,
                c.charter_type,
                CASE
                    WHEN COALESCE(c.cancelled, false) = true
                      OR LOWER(COALESCE(c.status, '')) = 'cancelled'
                    THEN 0
                    ELSE COALESCE(c.total_amount_due, 0)
                END AS total_amount_due,
                COALESCE(p.total_paid, c.amount_paid, c.paid_amount, 0)
                AS total_paid,
                COALESCE(nrr.nrr_amount, 0) AS nrr_amount,
                CASE
                    WHEN c.locked = true AND c.cancelled = false
                    THEN 'Reconciled'
                    WHEN c.cancelled = true THEN 'Cancelled'
                    ELSE 'Not Reconciled'
                END AS reconciliation_status,
                CASE
                    WHEN COALESCE(c.cancelled, false) = true
                      OR LOWER(COALESCE(c.status, '')) = 'cancelled'
                    THEN 0
                    ELSE GREATEST(
                        COALESCE(c.total_amount_due, 0)
                        - COALESCE(p.total_paid, c.amount_paid, c.paid_amount, 0),
                        0
                    )
                END AS balance,
                cl.client_name,
                cl.company_name,
                cl.email,
                COALESCE(cl.primary_phone, cl.phone) AS phone,
                v.passenger_capacity AS vehicle_capacity
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
            LEFT JOIN (
                SELECT charter_id, SUM(amount) AS total_paid
                FROM payments
                GROUP BY charter_id
            ) p ON c.charter_id = p.charter_id
            LEFT JOIN (
                SELECT charter_id, SUM(amount) AS nrr_amount
                FROM payments
                WHERE payment_label IN (
                    'NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer'
                )
                  AND payment_label NOT IN ('Deposit')
                GROUP BY charter_id
            ) nrr ON c.charter_id = nrr.charter_id
            WHERE c.charter_id = %s
            """,
            (charter_id,),
        )
        row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    result = dict(zip(cols, row, strict=False))
    result["total_amount_due"] = float(result.get("total_amount_due") or 0.0)
    result["total_paid"] = float(result.get("total_paid") or 0.0)
    result["balance"] = float(result.get("balance") or 0.0)
    result["nrr_amount"] = float(result.get("nrr_amount") or 0.0)
    return result


@router.get("/bookings/search")
def search_bookings(
    q: Annotated[str, Query(description="Search text")] = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
):
    q = (q or "").strip()
    if not q:
        return {"results": []}
    like = f"%{q}%"
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                COALESCE(cl.client_name, c.client_id::text) AS client_name
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE CAST(c.reserve_number AS TEXT) ILIKE %s
               OR COALESCE(cl.client_name, '') ILIKE %s
            ORDER BY c.charter_date DESC, c.charter_id DESC
            LIMIT %s
            """,
            (like, like, limit),
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
    return {"results": [dict(zip(cols, r, strict=False)) for r in rows]}


@router.patch("/bookings/{charter_id}")
def update_booking(
    request: Request,
    charter_id: Annotated[int, Path()],
    payload: dict[str, Any] | None = None,
):
    payload = payload or {}

    # Check if charter is locked
    with cursor() as cur:
        enforce_charter_not_locked(charter_id, cur)

    allowed_fields = [
        "vehicle_booked_id",
        "vehicle_number",
        "driver_name",
        "notes",
    ]
    updates = {k: v for k, v in payload.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail="no_valid_fields")
    set_clauses = ", ".join([f"{field} = %s" for field in updates])
    values = [*list(updates.values()), charter_id]
    with cursor() as cur:
        before_snapshot = _fetch_charter_snapshot(cur, charter_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="not_found")

        cur.execute(f"UPDATE charters SET {set_clauses}  WHERE charter_id = %s", values)
        after_snapshot = _fetch_charter_snapshot(cur, charter_id)
        if not after_snapshot:
            raise HTTPException(status_code=404, detail="not_found")

        ensure_audit_storage(cur.connection)
        record_audit_event(
            cur.connection,
            AuditEvent(
                module="bookings",
                entity_type="booking",
                entity_id=str(charter_id),
                action="update_booking",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=after_snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Booking updated through API",
            ),
            ensure_storage=False,
            commit=False,
        )
    return {
        "charter_id": after_snapshot.get("charter_id"),
        "vehicle_booked_id": after_snapshot.get("vehicle_booked_id"),
        "driver_name": after_snapshot.get("driver_name"),
        "notes": after_snapshot.get("notes"),
    }


def _validate_booking_input(payload: dict[str, Any]) -> None:
    """Validate required booking fields."""
    required = [
        "client_name",
        "charter_date",
        "pickup_time",
        "passenger_load",
        "total_amount_due",
    ]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing_fields: {', '.join(missing)}")


def _extract_booking_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize payload fields for booking."""
    return {
        "client_id": payload.get("client_id"),
        "client_name": (payload.get("client_name") or "").strip(),
        "phone": (payload.get("phone") or "").strip() or None,
        "email": (payload.get("email") or "").strip(),
        "billing_address": (payload.get("billing_address") or "").strip(),
        "city": (payload.get("city") or "").strip(),
        "province": (payload.get("province") or "").strip(),
        "zip_code": (payload.get("postal_code") or "").strip(),
        "charter_date": payload.get("charter_date"),
        "pickup_time": payload.get("pickup_time"),
        "passenger_count": int(payload.get("passenger_load") or payload.get("passenger_count") or 1),
        "vehicle_id": payload.get("vehicle_booked_id"),
        "assigned_driver_id": payload.get("assigned_driver_id"),
        "status": payload.get("status") or "Quote",
        "total_amount_due": float(payload.get("total_amount_due")) if payload.get("total_amount_due") is not None else 0.0,
        "client_notes": payload.get("customer_notes"),
        "driver_notes": payload.get("dispatcher_notes"),
        "vehicle_notes": payload.get("special_requests"),
        "itinerary": payload.get("itinerary") or [],
        "separate_customer_printout": payload.get("separate_customer_printout", False),
        "deposit_paid": float(payload.get("deposit_paid")) if payload.get("deposit_paid") else 0.0,
    }


def _resolve_or_create_client(cur, client_name: str, phone: str | None, fields: dict[str, Any]) -> int:
    """Lookup existing client or create new one."""
    client_id = fields.get("client_id")
    if not client_id:
        cur.execute(
            """
            SELECT client_id FROM clients
            WHERE COALESCE(client_name,'') = %s AND COALESCE(phone,'') = COALESCE(%s, '')
            LIMIT 1
            """,
            (client_name, phone),
        )
        row = cur.fetchone()
        if row:
            client_id = row[0]
        else:
            try:
                cur.execute("SAVEPOINT acct_seq")
                cur.execute("SELECT nextval('account_number_seq')")
                new_account_number = str(int(cur.fetchone()[0]))
                cur.execute("RELEASE SAVEPOINT acct_seq")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT acct_seq")
                cur.execute(
                    "SELECT MAX(CAST(account_number AS INTEGER)) FROM clients WHERE account_number ~ '^[0-9]+$'"
                )
                max_account = cur.fetchone()[0] or 7604
                new_account_number = str(int(max_account) + 1)

            cur.execute(
                """
                INSERT INTO clients (account_number, client_name, phone, email, billing_address, city, province, zip_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (account_number) DO NOTHING
                RETURNING client_id
                """,
                (new_account_number, client_name, phone, fields["email"], fields["billing_address"], fields["city"], fields["province"], fields["zip_code"]),
            )
            result_row = cur.fetchone()
            if result_row:
                client_id = result_row[0]
            else:
                cur.execute("SELECT MAX(CAST(account_number AS INTEGER)) FROM clients WHERE account_number ~ '^[0-9]+$'")
                max_account2 = cur.fetchone()[0] or 7604
                retry_number = str(int(max_account2) + 1)
                cur.execute(
                    """
                    INSERT INTO clients (account_number, client_name, phone, email, billing_address, city, province, zip_code)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING client_id
                    """,
                    (retry_number, client_name, phone, fields["email"], fields["billing_address"], fields["city"], fields["province"], fields["zip_code"]),
                )
                client_id = cur.fetchone()[0]
    return client_id


# SQL Constants for duplicate query elimination
_CHARGES_INSERT = "INSERT INTO charges (reserve_number, charge_type, amount, description) VALUES (%s, %s, %s, %s)"


def _insert_base_and_fees(cur, reserve_number: str, base_charge: float, airport_fee: float, additional_charges: float) -> None:
    """Insert base rate, airport fee, and additional charges."""
    if base_charge > 0:
        cur.execute(_CHARGES_INSERT, (reserve_number, "base_rate", base_charge, "Base charge"))
    if airport_fee > 0:
        cur.execute(_CHARGES_INSERT, (reserve_number, "airport_fee", airport_fee, "Airport fee"))
    if additional_charges > 0:
        cur.execute(_CHARGES_INSERT, (reserve_number, "additional", additional_charges, "Additional charges"))


def _insert_beverage_and_gratuity(cur, reserve_number: str, beverage_total: float, gratuity_percentage: float | None, gratuity_amount: float, gratuity_base: float, extra_gratuity_cash: float) -> float:
    """Insert beverage charges and gratuity; return inserted gratuity amount."""
    inserted_gratuity = 0.0

    if beverage_total > 0:
        cur.execute(_CHARGES_INSERT, (reserve_number, "additional", beverage_total, "Beverage service"))

    if gratuity_amount > 0:
        inserted_gratuity = gratuity_amount
        cur.execute(_CHARGES_INSERT, (reserve_number, "additional", gratuity_amount, "Gratuity (approved)"))
    elif gratuity_percentage:
        try:
            gratuity_percentage = float(gratuity_percentage)
            if gratuity_percentage > 0 and gratuity_base > 0:
                gratuity_calc = round(gratuity_base * gratuity_percentage / 100, 2)
                if gratuity_calc > 0:
                    inserted_gratuity = gratuity_calc
                    cur.execute(_CHARGES_INSERT, (reserve_number, "additional", gratuity_calc, f"Gratuity ({gratuity_percentage}% of charter charges)"))
        except Exception:
            pass

    if extra_gratuity_cash > 0:
        with suppress(Exception):
            cur.execute(_CHARGES_INSERT, (reserve_number, "additional", 0.0, f"Extra gratuity cash paid directly to driver (non-taxable): ${extra_gratuity_cash:.2f}"))

    return inserted_gratuity


def _insert_booking_charges(cur, reserve_number: str, payload: dict[str, Any], is_gst_exempt: bool, total_amount_due: float) -> None:
    """Insert all charge-type records."""
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except Exception:
            return default

    base_charge = _to_float(payload.get("base_charge"))
    airport_fee = _to_float(payload.get("airport_fee"))
    additional_charges = _to_float(payload.get("additional_charges_amount") or payload.get("additional_charges"))
    beverage_total = _to_float(payload.get("beverage_total"))
    charter_fee_amount = _to_float(payload.get("charter_fee_amount"))
    gratuity_percentage = payload.get("gratuity_percentage")
    gratuity_amount = _to_float(payload.get("gratuity_amount"))
    extra_gratuity_cash = _to_float(payload.get("extra_gratuity") or payload.get("gratuity_cash_amount"))

    # Insert base charges
    _insert_base_and_fees(cur, reserve_number, base_charge, airport_fee, additional_charges)

    # Calculate gratuity base
    gratuity_base = charter_fee_amount if charter_fee_amount > 0 else base_charge
    if gratuity_base <= 0 and total_amount_due > 0:
        gratuity_base = max(0.0, total_amount_due - beverage_total - additional_charges - airport_fee - extra_gratuity_cash)

    # Insert beverage and gratuity
    inserted_gratuity_amount = _insert_beverage_and_gratuity(cur, reserve_number, beverage_total, gratuity_percentage, gratuity_amount, gratuity_base, extra_gratuity_cash)

    # Insert GST if not exempt
    if not is_gst_exempt and total_amount_due > 0:
        # GST is charged on gratuity as well; only cash gratuity paid directly to the driver
        # stays outside the taxable booking total.
        gst_taxable_total = max(0.0, total_amount_due - extra_gratuity_cash)
        gst_amount = round(gst_taxable_total * 0.05 / 1.05, 2)
        if gst_amount > 0:
            cur.execute(_CHARGES_INSERT, (reserve_number, "gst", gst_amount, "GST (5% Alberta, tax-included)"))


def _insert_itinerary_routes(cur, charter_id: int, itinerary: list) -> None:
    """Insert itinerary stops as charter routes."""
    if not isinstance(itinerary, list) or len(itinerary) == 0:
        return

    for seq, stop in enumerate(itinerary, start=1):
        stop_type = stop.get("type", "stop")
        address = stop.get("address", "")
        time_str = stop.get("time24", "")
        stop_time = time_str if time_str else None

        if seq < len(itinerary):
            next_stop = itinerary[seq]
            next_address = next_stop.get("address", "")
            next_time = next_stop.get("time24", "")
            cur.execute(
                """
                INSERT INTO charter_routes (
                    charter_id, route_sequence, pickup_location, pickup_time,
                    dropoff_location, dropoff_time, event_type_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (charter_id, seq, address, stop_time, next_address, next_time, stop_type),
            )
        else:
            cur.execute(
                """
                INSERT INTO charter_routes (
                    charter_id, route_sequence, pickup_location, pickup_time,
                    dropoff_location, dropoff_time, event_type_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (charter_id, seq, "", None, address, stop_time, stop_type),
            )


def _validate_and_prepare_charter_data(cur, client_id: int, assigned_driver_id: int | None) -> dict[str, Any]:
    """Validate employee_id and fetch client GST exemption status."""
    if assigned_driver_id:
        cur.execute(
            "SELECT employee_id FROM employees WHERE employee_id = %s",
            (assigned_driver_id,),
        )
        if not cur.fetchone():
            assigned_driver_id = None

    cur.execute("SELECT gst_exempt FROM clients WHERE client_id = %s", (client_id,))
    client_row = cur.fetchone()
    is_gst_exempt = client_row[0] if client_row else False

    return {"assigned_driver_id": assigned_driver_id, "is_gst_exempt": is_gst_exempt}


@router.post("/bookings/create")
def create_booking(request: Request, payload: dict[str, Any] | None = None):
    """Create a new charter booking with minimal required fields."""
    payload = payload or {}
    _validate_booking_input(payload)
    fields = _extract_booking_fields(payload)

    # Derive pickup/dropoff from itinerary if present
    itinerary = fields["itinerary"]
    pickup_address = None
    dropoff_address = None
    if isinstance(itinerary, list) and itinerary:
        first = itinerary[0] or {}
        pickup_address = first.get("address")
        last = itinerary[-1] or {}
        dropoff_address = last.get("address")

    # Resolve client_id by name/phone if not provided; create if missing
    with cursor() as cur:
        client_id = _resolve_or_create_client(cur, fields["client_name"], fields["phone"], fields)
        reserve_number = _next_reserve_number(cur)

        # Validate employee and fetch GST exemption
        validated_data = _validate_and_prepare_charter_data(cur, client_id, fields["assigned_driver_id"])
        fields["assigned_driver_id"] = validated_data["assigned_driver_id"]
        is_gst_exempt = validated_data["is_gst_exempt"]

        # Insert into charters table using correct column names
        cur.execute(
            """
            INSERT INTO charters (
                charter_date, client_id, reserve_number, passenger_count, vehicle_id, employee_id,
                pickup_address, dropoff_address, pickup_time, total_amount_due, status,
                separate_customer_printout, client_notes, driver_notes, vehicle_notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING charter_id, reserve_number, status
            """,
            (
                fields["charter_date"],
                client_id,
                reserve_number,
                fields["passenger_count"],
                fields["vehicle_id"],
                fields["assigned_driver_id"],
                pickup_address,
                dropoff_address,
                fields["pickup_time"],
                fields["total_amount_due"],
                fields["status"],
                fields["separate_customer_printout"],
                fields["client_notes"],
                fields["driver_notes"],
                fields["vehicle_notes"],
            ),
        )
        new_row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
        charter_id = new_row[0]

        # Insert itinerary stops into charter_routes table
        _insert_itinerary_routes(cur, charter_id, itinerary)

        # Insert all charges using helper
        _insert_booking_charges(cur, reserve_number, payload, is_gst_exempt, fields["total_amount_due"])

        # Insert deposit payment if provided
        deposit = fields["deposit_paid"]
        if deposit > 0:
            cur.execute(
                """
                INSERT INTO payments (
                    charter_id,
                    reserve_number,
                    amount,
                    payment_date,
                    payment_method,
                    status,
                    notes) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    charter_id,
                    reserve_number,
                    deposit,
                    fields["charter_date"],
                    "cash",
                    "paid",
                    "Deposit paid at booking",
                ),
            )
        # End cursor context: auto-commit

    with cursor() as cur:
        after_snapshot = _fetch_charter_snapshot(cur, charter_id)
        ensure_audit_storage(cur.connection)
        record_audit_event(
            cur.connection,
            AuditEvent(
                module="bookings",
                entity_type="booking",
                entity_id=str(charter_id),
                action="create_booking",
                source="api",
                actor=_audit_actor(request),
                before=None,
                after=after_snapshot
                or {
                    "charter_id": charter_id,
                    "reserve_number": new_row[1],
                    "status": new_row[2],
                },
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Booking created through API",
            ),
            ensure_storage=False,
            commit=False,
        )

    return dict(zip(cols, new_row, strict=False))
