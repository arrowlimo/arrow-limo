from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

from ..db import cursor


router = APIRouter(prefix="/api", tags=["bookings"])


@router.get("/bookings")
def list_bookings():
    sql = (
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
        ORDER BY c.charter_date DESC, c.charter_id DESC 
        LIMIT 50
        """
    )
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
                "client_name": rec.get("client_name", "") or rec.get("client_id", "") or "",
                "vehicle_type_requested": rec.get("vehicle_type_requested", ""),
                "vehicle_booked_id": rec.get("vehicle_booked_id", ""),
                "driver_name": rec.get("driver_name", ""),
                "vehicle_description": rec.get("vehicle_description", ""),
                "passenger_load": rec.get("passenger_load", 0),
                "vehicle_capacity": rec.get("vehicle_capacity", 0),
                "retainer": float(rec.get("retainer", 0) or 0.0),
                "odometer_start": rec.get("odometer_start", ""),
                "odometer_end": rec.get("odometer_end", ""),
                "fuel_added": rec.get("fuel_added", ""),
                "vehicle_notes": rec.get("vehicle_notes", "") or rec.get("notes", ""),
                "itinerary_stops": 0,
                "reserve_number": rec.get("reserve_number", ""),
                "pickup_address": rec.get("pickup_address", ""),
                "dropoff_address": rec.get("dropoff_address", ""),
                "status": rec.get("status", ""),
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
        cur.execute("SELECT charter_id, vehicle_booked_id, driver_name, notes FROM charters WHERE charter_id=%s", (charter_id,))
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
    required = ["client_name", "charter_date", "pickup_time", "passenger_load", "total_amount_due"]
    missing = [k for k in required if not payload.get(k)]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing_fields: {', '.join(missing)}")

    client_id = payload.get("client_id")
    client_name = (payload.get("client_name") or "").strip()
    phone = (payload.get("phone") or "").strip()
    email = (payload.get("email") or "").strip()

    charter_date = payload.get("charter_date")
    pickup_time = payload.get("pickup_time")
    passenger_load = int(payload.get("passenger_load") or 0)
    vehicle_type_requested = payload.get("vehicle_type_requested")
    vehicle_booked_id = payload.get("vehicle_booked_id")
    status = payload.get("status") or "Quote"
    total_amount_due = payload.get("total_amount_due")

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
                cur.execute("SELECT MAX(CAST(account_number AS INTEGER)) FROM clients WHERE account_number ~ '^[0-9]+$'")
                max_account = cur.fetchone()[0] or 7604
                new_account_number = str(int(max_account) + 1)
                
                # Create a basic client record
                cur.execute(
                    """
                    INSERT INTO clients (account_number, client_name, phone, email)
                    VALUES (%s, %s, %s, %s)
                    RETURNING client_id
                    """,
                    (new_account_number, client_name, phone, email),
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
            cur.execute("SELECT MAX(CAST(reserve_number AS INTEGER)) FROM charters WHERE reserve_number ~ '^\\d+$'")
            max_val = cur.fetchone()[0] or 0
            reserve_number = f"{int(max_val) + 1:06d}"

        # Optional: map assigned_driver_id to driver_name for existing schema
        driver_name = None
        assigned_driver_id = payload.get("assigned_driver_id")
        if assigned_driver_id:
            cur.execute(
                """
                SELECT first_name, last_name FROM employees WHERE employee_id = %s
                """,
                (assigned_driver_id,),
            )
            emp = cur.fetchone()
            if emp:
                first, last = emp[0] or "", emp[1] or ""
                driver_name = (f"{first} {last}").strip() or None

        # Check if client is GST exempt
        cur.execute("SELECT gst_exempt FROM clients WHERE client_id = %s", (client_id,))
        client_row = cur.fetchone()
        is_gst_exempt = client_row[0] if client_row else False
        
        # Get separate_customer_printout flag from payload
        separate_customer_printout = payload.get("separate_customer_printout", False)
        
        # Insert into charters table using known columns
        cur.execute(
            """
            INSERT INTO charters (
                charter_date,
                client_id,
                reserve_number,
                passenger_load,
                vehicle_booked_id,
                vehicle_type_requested,
                driver_name,
                pickup_address,
                dropoff_address,
                total_amount_due,
                status,
                separate_customer_printout
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING charter_id, reserve_number, status
            """,
            (
                charter_date,
                client_id,
                reserve_number,
                passenger_load,
                vehicle_booked_id,
                vehicle_type_requested,
                driver_name,
                pickup_address,
                dropoff_address,
                total_amount_due,
                status,
                separate_customer_printout,
            ),
        )
        new_row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]

        # Insert charges line items (business key: reserve_number)
        base_charge = payload.get("base_charge")
        airport_fee = payload.get("airport_fee")
        additional_charges = payload.get("additional_charges_amount") or payload.get("additional_charges")
        
        if base_charge:
            try:
                base_charge = float(base_charge)
                if base_charge > 0:
                    cur.execute(
                        """
                        INSERT INTO charges (reserve_number, charge_type, amount, description)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (reserve_number, "base_rate", base_charge, "Base charge"),
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
                        (reserve_number, "airport_fee", airport_fee, "Airport fee"),
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
                        (reserve_number, "additional", additional_charges, "Additional charges"),
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
                        (reserve_number, "additional", beverage_total, "Beverage service"),
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
                        (reserve_number, "additional", gratuity_amount, "Gratuity (custom)"),
                    )
            except Exception:
                pass
        elif gratuity_percentage:
            try:
                gratuity_percentage = float(gratuity_percentage)
                if gratuity_percentage > 0 and total_amount_due:
                    # Calculate gratuity as percentage of subtotal (before GST)
                    subtotal = float(total_amount_due) / 1.05  # Remove GST to get subtotal
                    gratuity_calc = round(subtotal * gratuity_percentage / 100, 2)
                    if gratuity_calc > 0:
                        cur.execute(
                            """
                            INSERT INTO charges (reserve_number, charge_type, amount, description)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (reserve_number, "additional", gratuity_calc, f"Gratuity ({gratuity_percentage}%)"),
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
                    (reserve_number, "gst", gst_amount, "GST (5% Alberta, tax-included)"),
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
                    notes
                ) VALUES (%s, %s, %s, %s, %s, %s)
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
