from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

from ..db import cursor
from ..utils.locked_charter import enforce_charter_not_locked

router = APIRouter(prefix="/api", tags=["bookings"])


@router.get("/bookings")
def list_bookings():
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
            CASE WHEN c.status = 'cancelled' THEN true ELSE false END AS cancelled,
            COALESCE(c.charter_type, 'standard') AS charter_type,
            '{}' AS exchange_of_services_details,
            '4000' AS gl_revenue_code,
            '6100' AS gl_expense_code,
            cl.client_name,
            v.passenger_capacity AS vehicle_capacity,
            c.total_amount_due,
            c.balance AS paid_amount,
            COALESCE(p.total_paid, 0) AS total_paid,
            (COALESCE(c.total_amount_due, 0) - COALESCE(p.total_paid, 0)) AS balance,
            CASE
                WHEN c.locked = TRUE AND c.status != 'cancelled' THEN 'Reconciled'
                WHEN c.status = 'cancelled' THEN 'Cancelled'
                WHEN c.locked = FALSE AND c.status != 'cancelled' THEN 'Not Reconciled'
                ELSE 'Unknown'
            END AS reconciliation_status,
            COALESCE(nrr.nrr_amount, 0) AS nrr_amount,
            CASE WHEN nrr.nrr_amount > 0 THEN TRUE ELSE FALSE END AS nrr_received,
            EXISTS (
                SELECT 1
                FROM beverage_orders bo
                WHERE bo.reserve_number = c.reserve_number
                  AND bo.order_date >= date_trunc('week', CURRENT_DATE)
                  AND bo.order_date < date_trunc('week', CURRENT_DATE) + interval '7 days') AS beverage_orders_this_week
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
                payment_label IN ('NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer')
                OR payment_key ILIKE '%NRR%'
                OR payment_key ILIKE '%NRD%')
            AND payment_label NOT IN ('Deposit', 'Security Deposit', 'Damage Deposit')
            GROUP BY reserve_number) nrr ON nrr.reserve_number = c.reserve_number
        ORDER BY c.charter_date DESC, c.charter_id DESC
        LIMIT 50
        """
    with cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
    items: list[dict[str, Any]] = []
    for r in rows:
        rec = dict(zip(cols, r, strict=False))
        
        items.append(
            {
                "charter_id": rec.get("charter_id", ""),
                "charter_date": str(rec.get("charter_date", "")),
                "client_name": rec.get("client_name", "")
                or rec.get("client_id", "")
                or "",
                "client_id": rec.get("client_id", ""),
                "vehicle": rec.get("vehicle", ""),
                "vehicle_description": rec.get("vehicle_description", ""),
                "vehicle_id": rec.get("vehicle_id", ""),
                "driver_name": rec.get("driver_name", ""),
                "passenger_count": rec.get("passenger_count", 0),
                "passenger_load": rec.get("passenger_count", 0),  # Alias for frontend compatibility
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
                "pickup_time": str(rec.get("pickup_time", "")) if rec.get("pickup_time") else "",
                "dropoff_address": rec.get("dropoff_address", ""),
                "status": rec.get("status", ""),
                "closed": bool(rec.get("closed", False)),
                "cancelled": bool(rec.get("cancelled", False)),
                "charter_type": rec.get("charter_type", "standard"),
                "exchange_of_services_details": rec.get(
                    "exchange_of_services_details", {}
                ),
                "gl_revenue_code": rec.get("gl_revenue_code", "4000"),
                "gl_expense_code": rec.get("gl_expense_code", "6100"),
                "reconciliation_status": rec.get("reconciliation_status", "Unknown"),
                "total_amount_due": float(rec.get("total_amount_due", 0) or 0.0),
                "paid_amount": float(rec.get("paid_amount", 0) or 0.0),
                "total_paid": float(rec.get("total_paid", 0) or 0.0),
                "balance": float(rec.get("balance", 0) or 0.0),
                "nrr_amount": float(rec.get("nrr_amount", 0) or 0.0),
                "nrr_received": bool(rec.get("nrr_received", False)),
                "beverage_orders_this_week": bool(
                    rec.get("beverage_orders_this_week", False)
                ),
            }
        )
    return {"bookings": items}


@router.get("/bookings/{charter_id}")
def get_booking(charter_id: int = Path(...)):
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                c.charter_id,
                c.charter_date,
                c.client_id,
                c.reserve_number,
                c.passenger_load,
                c.vehicle_booked_id,
                c.vehicle_description,
                c.vehicle_type_requested,
                c.driver_name,
                c.retainer,
                c.odometer_start,
                c.odometer_end,
                c.fuel_added,
                c.vehicle_notes,
                c.notes,
                c.pickup_address,
                c.dropoff_address,
                c.status,
                cl.client_name,
                v.passenger_capacity AS vehicle_capacity
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            LEFT JOIN vehicles v ON CAST(c.vehicle_booked_id AS TEXT) = CAST(v.vehicle_number AS TEXT)
            WHERE c.charter_id = %s
            """,
            (charter_id,),
        )
        row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return dict(zip(cols, row, strict=False))


@router.get("/bookings/search")
def search_bookings(
    q: str = Query("", description="Search text"),
    limit: int = Query(25, ge=1, le=200),
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
def update_booking(charter_id: int = Path(...), payload: dict[str, Any] | None = None):
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
        cur.execute(f"UPDATE charters SET {set_clauses} WHERE charter_id = %s", values)
        cur.execute(
            "SELECT charter_id, vehicle_booked_id, driver_name, notes FROM charters WHERE charter_id=%s",
            (charter_id,),
        )
        row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return dict(zip(cols, row, strict=False))


@router.post("/bookings/create")
def create_booking(payload: dict[str, Any] | None = None):
    """Create a new charter booking with minimal required fields.

    This endpoint focuses on inserting into the `charters` table and generating a
    `reserve_number`. It uses business keys appropriately and avoids guessing
    schema beyond verified columns from existing queries.
    """
    payload = payload or {}
    required = [
        "client_name",
        "charter_date",
        "pickup_time",
        "passenger_load",
        "total_amount_due",
    ]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(
            status_code=400, detail=f"missing_fields: {', '.join(missing)}"
        )

    client_id = payload.get("client_id")
    client_name = (payload.get("client_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip()
    billing_address = (payload.get("billing_address") or "").strip()
    city = (payload.get("city") or "").strip()
    province = (payload.get("province") or "").strip()
    zip_code = (payload.get("postal_code") or "").strip()  # Fixed: DB column is zip_code

    charter_date = payload.get("charter_date")
    pickup_time = payload.get("pickup_time")
    passenger_count = int(payload.get("passenger_load") or payload.get("passenger_count") or 1)  # Default to 1 passenger
    vehicle_id = payload.get("vehicle_booked_id")  # Fixed: DB column is vehicle_id
    assigned_driver_id = payload.get("assigned_driver_id")  # Use employee_id instead of driver_name
    status = payload.get("status") or "Quote"
    total_amount_due = payload.get("total_amount_due")
    
    # Notes fields
    client_notes = payload.get("customer_notes")  # Fixed: DB column is client_notes
    driver_notes = payload.get("dispatcher_notes")  # Fixed: DB column is driver_notes
    vehicle_notes = payload.get("special_requests")  # Maps to vehicle_notes

    # Derive pickup/dropoff from itinerary if present
    itinerary = payload.get("itinerary") or []
    pickup_address = None
    dropoff_address = None
    if isinstance(itinerary, list) and itinerary:
        first = itinerary[0] or {}
        pickup_address = first.get("address")
        last = itinerary[-1] or {}
        dropoff_address = last.get("address")

    # Resolve client_id by name/phone if not provided; create if missing
    with cursor() as cur:
        if not client_id:
            cur.execute(
                """
                SELECT client_id FROM clients
                WHERE COALESCE(client_name,'') = %s AND COALESCE(phone,'') = %s
                LIMIT 1
                """,
                (client_name, phone),
            )
            row = cur.fetchone()
            if row:
                client_id = row[0]
            else:
                # Generate account_number (max numeric + 1)
                cur.execute(
                    "SELECT MAX(CAST(account_number AS INTEGER)) FROM clients WHERE account_number ~ '^[0-9]+$'"
                )
                max_account = cur.fetchone()[0] or 7604
                new_account_number = str(int(max_account) + 1)

                # Create a basic client record
                cur.execute(
                    """
                    INSERT INTO clients (account_number, client_name, phone, email, billing_address, city, province, zip_code)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING client_id
                    """,
                    (new_account_number, client_name, phone, email, billing_address, city, province, zip_code),
                )
                client_id = cur.fetchone()[0]

        # Generate reserve_number via sequence if available; else fallback to max+1
        reserve_number = None
        try:
            cur.execute("SELECT nextval('reserve_number_seq')")
            seq_val = cur.fetchone()[0]
            reserve_number = f"{int(seq_val):06d}"
        except Exception:
            # Fallback: derive from current max reserve_number
            cur.execute(
                "SELECT MAX(CAST(reserve_number AS INTEGER)) FROM charters WHERE reserve_number ~ '^\\d+$'"
            )
            max_val = cur.fetchone()[0] or 0
            reserve_number = f"{int(max_val) + 1:06d}"

        # Validate employee_id if provided
        if assigned_driver_id:
            cur.execute(
                "SELECT employee_id FROM employees WHERE employee_id = %s",
                (assigned_driver_id,),
            )
            if not cur.fetchone():
                assigned_driver_id = None  # Invalid employee_id, set to NULL

        # Check if client is GST exempt
        cur.execute("SELECT gst_exempt FROM clients WHERE client_id = %s", (client_id,))
        client_row = cur.fetchone()
        is_gst_exempt = client_row[0] if client_row else False

        # Get separate_customer_printout flag from payload
        separate_customer_printout = payload.get("separate_customer_printout", False)

        # Insert into charters table using correct column names
        cur.execute(
            """
            INSERT INTO charters (
                charter_date,
                client_id,
                reserve_number,
                passenger_count,
                vehicle_id,
                employee_id,
                pickup_address,
                dropoff_address,
                pickup_time,
                total_amount_due,
                status,
                separate_customer_printout,
                client_notes,
                driver_notes,
                vehicle_notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING charter_id, reserve_number, status
            """,
            (
                charter_date,
                client_id,
                reserve_number,
                passenger_count,
                vehicle_id,
                assigned_driver_id,
                pickup_address,
                dropoff_address,
                pickup_time,
                total_amount_due,
                status,
                separate_customer_printout,
                client_notes,
                driver_notes,
                vehicle_notes,
            ),
        )
        new_row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
        charter_id = new_row[0]  # Extract charter_id for charter_routes

        # Insert itinerary stops into charter_routes table
        if isinstance(itinerary, list) and len(itinerary) > 0:
            # Create route segments from consecutive stops
            for seq, stop in enumerate(itinerary, start=1):
                stop_type = stop.get("type", "stop")
                address = stop.get("address", "")
                time_str = stop.get("time24", "")
                
                # Parse time string to time object
                stop_time = None
                if time_str:
                    try:
                        # time_str is in HH:MM format
                        stop_time = time_str
                    except Exception:
                        stop_time = None
                
                # Determine pickup/dropoff based on stop type
                # For route segments, each stop creates a row with that location as pickup
                # and next stop as dropoff (except last stop)
                if seq < len(itinerary):
                    # Not the last stop - create segment to next stop
                    next_stop = itinerary[seq]
                    next_address = next_stop.get("address", "")
                    next_time = next_stop.get("time24", "")
                    
                    cur.execute(
                        """
                        INSERT INTO charter_routes (
                            charter_id,
                            route_sequence,
                            pickup_location,
                            pickup_time,
                            dropoff_location,
                            dropoff_time,
                            event_type_code
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            charter_id,
                            seq,
                            address,
                            stop_time,
                            next_address,
                            next_time,
                            stop_type
                        )
                    )
                else:
                    # Last stop - create row with just this location as dropoff
                    cur.execute(
                        """
                        INSERT INTO charter_routes (
                            charter_id,
                            route_sequence,
                            pickup_location,
                            pickup_time,
                            dropoff_location,
                            dropoff_time,
                            event_type_code
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            charter_id,
                            seq,
                            "",  # No pickup for last segment
                            None,
                            address,  # Last stop is final dropoff
                            stop_time,
                            stop_type
                        )
                    )

        # Insert charges line items (business key: reserve_number)
        base_charge = payload.get("base_charge")
        airport_fee = payload.get("airport_fee")
        additional_charges = payload.get("additional_charges_amount") or payload.get(
            "additional_charges"
        )

        if base_charge:
            try:
                base_charge = float(base_charge)
                if base_charge > 0:
                    cur.execute(
                        """
                        INSERT INTO charges (reserve_number, charge_type, amount, description)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            reserve_number,
                            "base_rate",
                            base_charge,
                            "Base charge",
                        ),
                    )
            except Exception:
                pass

        if airport_fee:
            try:
                airport_fee = float(airport_fee)
                if airport_fee > 0:
                    cur.execute(
                        """
                        INSERT INTO charges (reserve_number, charge_type, amount, description)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            reserve_number,
                            "airport_fee",
                            airport_fee,
                            "Airport fee",
                        ),
                    )
            except Exception:
                pass

        if additional_charges:
            try:
                additional_charges = float(additional_charges)
                if additional_charges > 0:
                    cur.execute(
                        """
                        INSERT INTO charges (reserve_number, charge_type, amount, description)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            reserve_number,
                            "additional",
                            additional_charges,
                            "Additional charges",
                        ),
                    )
            except Exception:
                pass

        # Insert beverage charges from cart (taxable, not included in cart price)
        beverage_total = payload.get("beverage_total")
        if beverage_total:
            try:
                beverage_total = float(beverage_total)
                if beverage_total > 0:
                    cur.execute(
                        """
                        INSERT INTO charges (reserve_number, charge_type, amount, description)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            reserve_number,
                            "additional",
                            beverage_total,
                            "Beverage service",
                        ),
                    )
            except Exception:
                pass

        # Insert gratuity (percentage-based: 18% default, or custom amount)
        gratuity_percentage = payload.get("gratuity_percentage")  # e.g., 18.0 for 18%
        gratuity_amount = payload.get("gratuity_amount")  # Override with fixed amount

        if gratuity_amount:
            try:
                gratuity_amount = float(gratuity_amount)
                if gratuity_amount > 0:
                    cur.execute(
                        """
                        INSERT INTO charges (reserve_number, charge_type, amount, description)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            reserve_number,
                            "additional",
                            gratuity_amount,
                            "Gratuity (custom)",
                        ),
                    )
            except Exception:
                pass
        elif gratuity_percentage:
            try:
                gratuity_percentage = float(gratuity_percentage)
                if gratuity_percentage > 0 and total_amount_due:
                    # Calculate gratuity as percentage of subtotal (before GST)
                    subtotal = (
                        float(total_amount_due) / 1.05
                    )  # Remove GST to get subtotal
                    gratuity_calc = round(subtotal * gratuity_percentage / 100, 2)
                    if gratuity_calc > 0:
                        cur.execute(
                            """
                            INSERT INTO charges (reserve_number, charge_type, amount, description)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (
                                reserve_number,
                                "additional",
                                gratuity_calc,
                                f"Gratuity ({gratuity_percentage}%)",
                            ),
                        )
            except Exception:
                pass

        # Calculate and insert GST (tax-included: gst = total * 0.05 / 1.05)
        # Skip if client is GST exempt
        if not is_gst_exempt and total_amount_due and total_amount_due > 0:
            gst_amount = round(float(total_amount_due) * 0.05 / 1.05, 2)
            if gst_amount > 0:
                cur.execute(
                    """
                    INSERT INTO charges (reserve_number, charge_type, amount, description)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        reserve_number,
                        "gst",
                        gst_amount,
                        "GST (5% Alberta, tax-included)",
                    ),
                )

        # Insert deposit payment if provided (business key: reserve_number)
        deposit = payload.get("deposit_paid")
        try:
            deposit = float(deposit) if deposit is not None else 0.0
        except Exception:
            deposit = 0.0
        if deposit and deposit > 0:
            cur.execute(
                """
                INSERT INTO payments (
                    reserve_number,
                    amount,
                    payment_date,
                    payment_method,
                    status,
                    notes) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    reserve_number,
                    deposit,
                    charter_date,
                    "cash",
                    "paid",
                    "Deposit paid at booking",
                ),
            )
        # End cursor context: auto-commit

    return dict(zip(cols, new_row, strict=False))
