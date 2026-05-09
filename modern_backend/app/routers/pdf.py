"""
PDF Generation Endpoints
"""

import json
from datetime import datetime
from io import BytesIO
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from pypdf import PdfReader, PdfWriter

from ..db import cursor
from ..services.pdf_generator import (
    generate_charter_pdf,
    generate_confirmation_letter_pdf,
    generate_t4_pdf,
)
from ..services.pdf_layout_settings import (
    apply_pdf_layout_preset,
    default_pdf_layout_settings,
    load_pdf_layout_settings,
    pdf_layout_settings_schema,
    reset_pdf_layout_settings,
    save_pdf_layout_settings,
)

router = APIRouter(prefix="/api", tags=["pdf"])


@router.get("/pdf-layout-settings")
def get_pdf_layout_settings():
    """Get editable layout settings used by charter PDF generation."""
    return load_pdf_layout_settings()


@router.get("/pdf-layout-settings/defaults")
def get_pdf_layout_settings_defaults():
    """Get default layout settings for charter PDF generation."""
    return default_pdf_layout_settings()


@router.get("/pdf-layout-settings/schema")
def get_pdf_layout_settings_schema():
    """Get setting metadata (type/range/options) for editor UIs."""
    return pdf_layout_settings_schema()


@router.put(
    "/pdf-layout-settings",
    responses={
        400: {"description": "Request body must be a JSON object"},
        500: {"description": "Failed to save layout settings"},
    },
)
def update_pdf_layout_settings(
    settings_patch: Annotated[dict[str, Any], Body(...)],
):
    """Update layout settings (partial patch) for charter PDF generation."""
    if not isinstance(settings_patch, dict):
        raise HTTPException(
            status_code=400, detail="Request body must be a JSON object"
        )
    try:
        return save_pdf_layout_settings(settings_patch)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to save layout settings: {e!s}"
        )


@router.post(
    "/pdf-layout-settings/reset",
    responses={
        500: {"description": "Failed to reset layout settings"},
    },
)
def reset_pdf_settings_to_default():
    """Reset current layout settings to defaults."""
    try:
        return reset_pdf_layout_settings()
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to reset layout settings: {e!s}"
        )


@router.post(
    "/pdf-layout-settings/presets/{preset_name}",
    responses={
        400: {"description": "Unknown preset name"},
        500: {"description": "Failed to apply preset"},
    },
)
def apply_pdf_layout_settings_preset(
    preset_name: Annotated[str, Path(...)],
):
    """Apply a built-in layout preset (default, compact, comfortable)."""
    try:
        return apply_pdf_layout_preset(preset_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to apply preset: {e!s}"
        )


def _normalize_exchange_details(charter_data: dict) -> None:
    """Normalize JSON payloads loaded from PostgreSQL."""
    if isinstance(charter_data.get("exchange_of_services_details"), str):
        try:
            charter_data["exchange_of_services_details"] = json.loads(
                charter_data["exchange_of_services_details"]
            )
        except Exception:
            charter_data["exchange_of_services_details"] = {}
    elif not charter_data.get("exchange_of_services_details"):
        charter_data["exchange_of_services_details"] = {}


def _parse_jsonish(value: Any, default: Any):
    if value in (None, "", []):
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def _coerce_order_ids(value: Any) -> list[int]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        parsed = _parse_jsonish(value, None)
        if isinstance(parsed, list):
            raw_items = parsed
        else:
            raw_items = [part.strip() for part in str(value).split(",")]

    order_ids: list[int] = []
    for item in raw_items:
        candidate = item.get("order_id") if isinstance(item, dict) else item
        try:
            order_ids.append(int(candidate))
        except (TypeError, ValueError):
            continue
    return order_ids


def _resolve_client_details(cur, charter_data: dict) -> None:
    client_id = charter_data.get("client_id")
    if not client_id:
        return

    cur.execute(
        """
        SELECT
            client_name,
            company_name,
            email,
            COALESCE(primary_phone, phone) AS phone,
            address_line1,
            city,
            province,
            zip_code
        FROM clients
        WHERE client_id = %s
        """,
        (client_id,),
    )
    row = cur.fetchone()
    if not row:
        return

    columns = [desc[0] for desc in cur.description]
    for key, value in dict(zip(columns, row, strict=False)).items():
        if not charter_data.get(key):
            charter_data[key] = value


def _resolve_vehicle_details(cur, charter_data: dict) -> None:
    vehicle_pk = charter_data.get("vehicle_id")
    if not vehicle_pk:
        return

    cur.execute(
        """
        SELECT
            vehicle_number,
            license_plate,
            passenger_capacity,
            COALESCE(description, TRIM(COALESCE(make, '') || ' ' || COALESCE(model, ''))) AS vehicle_description,
            vehicle_type
        FROM vehicles
        WHERE vehicle_id = %s
        """,
        (vehicle_pk,),
    )
    row = cur.fetchone()
    if not row:
        return

    columns = [desc[0] for desc in cur.description]
    vehicle = dict(zip(columns, row, strict=False))
    charter_data.setdefault("vehicle_number", vehicle.get("vehicle_number"))
    charter_data.setdefault("license_plate", vehicle.get("license_plate"))
    charter_data.setdefault("passenger_capacity", vehicle.get("passenger_capacity"))
    if not charter_data.get("vehicle"):
        charter_data["vehicle"] = vehicle.get("vehicle_number")
    if not charter_data.get("vehicle_id"):
        charter_data["vehicle_id"] = vehicle.get("vehicle_number")
    if not charter_data.get("vehicle_description"):
        charter_data["vehicle_description"] = vehicle.get("vehicle_description")
    if not charter_data.get("vehicle_type_requested"):
        charter_data["vehicle_type_requested"] = vehicle.get("vehicle_type")


def _resolve_driver_details(cur, charter_data: dict) -> None:
    employee_id = (
        charter_data.get("assigned_driver_id")
        or charter_data.get("employee_id")
        or charter_data.get("chauffeur_id")
    )
    if not employee_id:
        return

    cur.execute(
        """
        SELECT
            full_name,
            employee_number,
            driver_license_number,
            COALESCE(hourly_pay_rate, hourly_rate) AS hourly_rate
        FROM employees
        WHERE employee_id = %s
        """,
        (employee_id,),
    )
    row = cur.fetchone()
    if not row:
        return

    columns = [desc[0] for desc in cur.description]
    driver = dict(zip(columns, row, strict=False))
    if not charter_data.get("driver_name"):
        charter_data["driver_name"] = driver.get("full_name")
    if not charter_data.get("driver"):
        charter_data["driver"] = driver.get("full_name")
    if not charter_data.get("employee_number"):
        charter_data["employee_number"] = driver.get("employee_number")
    if not charter_data.get("driver_license_number"):
        charter_data["driver_license_number"] = driver.get(
            "driver_license_number"
        )
    if not charter_data.get("driver_hourly_rate"):
        charter_data["driver_hourly_rate"] = driver.get("hourly_rate")


def _load_beverage_items(cur, charter_data: dict) -> list[dict[str, Any]]:
    charter_id = charter_data.get("charter_id")
    beverages: list[dict[str, Any]] = []

    if charter_id:
        cur.execute(
            """
            SELECT item_name, quantity
            FROM charter_beverages
            WHERE charter_id = %s
            ORDER BY id
            """,
            (charter_id,),
        )
        beverage_columns = [desc[0] for desc in cur.description]
        beverages = [dict(zip(beverage_columns, row, strict=False)) for row in cur.fetchall()]
        if beverages:
            return beverages

    order_ids = _coerce_order_ids(
        charter_data.get("beverage_cart_ids")
        or charter_data.get("cart_order_list")
    )
    if not order_ids and charter_data.get("reserve_number"):
        cur.execute(
            """
            SELECT order_id
            FROM beverage_orders
            WHERE reserve_number = %s
            ORDER BY order_date, order_id
            """,
            (charter_data.get("reserve_number"),),
        )
        order_ids = [row[0] for row in cur.fetchall()]

    if not order_ids:
        return []

    placeholders = ", ".join(["%s"] * len(order_ids))
    cur.execute(
        f"""
        SELECT item_name, quantity
        FROM beverage_order_items
        WHERE order_id IN ({placeholders})
        ORDER BY order_id, item_line_id
        """,
        tuple(order_ids),
    )
    beverage_columns = [desc[0] for desc in cur.description]
    return [dict(zip(beverage_columns, row, strict=False)) for row in cur.fetchall()]


def _build_payload_routes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    routes = payload.get("routes") or []
    normalized_routes: list[dict[str, Any]] = []
    for index, route in enumerate(routes, start=1):
        if not isinstance(route, dict):
            continue
        normalized_routes.append(
            {
                "route_sequence": index,
                "event_type_code": route.get("event_type_code")
                or route.get("type"),
                "address": route.get("address") or route.get("location"),
                "stop_time": route.get("stop_time") or route.get("time"),
                "at_by": route.get("at_by") or "at",
                "route_notes": route.get("route_notes") or route.get("notes"),
            }
        )
    return normalized_routes


def _build_payload_charges(payload: dict[str, Any]) -> list[dict[str, Any]]:
    existing = payload.get("charges") or []
    if existing:
        return existing

    def _amount(key: str) -> float:
        try:
            return float(payload.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0

    charges: list[dict[str, Any]] = []
    charter_fee = _amount("charter_fee_amount")
    if charter_fee:
        charges.append(
            {
                "charge_type": "base_rate",
                "description": "Charter Fee",
                "amount": charter_fee,
            }
        )

    beverage_total = _amount("beverage_total")
    if beverage_total:
        charges.append(
            {
                "charge_type": "additional",
                "description": "Beverages",
                "amount": beverage_total,
            }
        )

    fuel_total = _amount("fuel_litres") * _amount("fuel_price")
    if fuel_total:
        charges.append(
            {
                "charge_type": "additional",
                "description": "Fuel",
                "amount": fuel_total,
            }
        )

    for charge in _parse_jsonish(payload.get("custom_charges"), []):
        if not isinstance(charge, dict):
            continue
        charges.append(
            {
                "charge_type": "additional",
                "description": charge.get("description") or "Custom Charge",
                "amount": charge.get("amount") or 0,
            }
        )

    gratuity = _amount("gratuity_amount")
    if gratuity:
        charges.append(
            {
                "charge_type": "gratuity",
                "description": "Gratuity",
                "amount": gratuity,
            }
        )

    extra_gratuity = _amount("extra_gratuity")
    if extra_gratuity:
        charges.append(
            {
                "charge_type": "additional",
                "description": "Extra Gratuity",
                "amount": extra_gratuity,
            }
        )

    gst_amount = _amount("gst_amount")
    if gst_amount:
        charges.append(
            {"charge_type": "gst", "description": "GST", "amount": gst_amount}
        )

    if not charges:
        total_due = _amount("grand_total") or _amount("total_amount_due")
        if total_due:
            charges.append(
                {
                    "charge_type": "service_fee",
                    "description": "Service Fee",
                    "amount": total_due,
                }
            )

    return charges


def _apply_pdf_field_aliases(charter_data: dict[str, Any]) -> dict[str, Any]:
    if not charter_data.get("passenger_load"):
        charter_data["passenger_load"] = charter_data.get("passenger_count")
    if not charter_data.get("notes"):
        charter_data["notes"] = charter_data.get("client_notes")
    if not charter_data.get("booking_notes"):
        charter_data["booking_notes"] = charter_data.get("driver_notes")
    if not charter_data.get("special_requirements"):
        charter_data["special_requirements"] = charter_data.get("vehicle_notes")
    if not charter_data.get("fuel_added"):
        charter_data["fuel_added"] = charter_data.get("fuel_added_liters") or charter_data.get("fuel_litres")
    if not charter_data.get("total_amount_due"):
        charter_data["total_amount_due"] = charter_data.get("grand_total") or charter_data.get("subtotal")
    if not charter_data.get("total_paid"):
        charter_data["total_paid"] = charter_data.get("amount_paid") or charter_data.get("paid_amount") or 0
    if not charter_data.get("vehicle_id"):
        charter_data["vehicle_id"] = charter_data.get("vehicle_number") or charter_data.get("vehicle")
    if not charter_data.get("driver_name"):
        charter_data["driver_name"] = charter_data.get("driver")
    return charter_data


def _build_run_sheet_payload(payload: dict[str, Any]) -> dict[str, Any]:
    charter_data = dict(payload or {})
    charter_data["routes"] = _build_payload_routes(charter_data)
    charter_data["charges"] = _build_payload_charges(charter_data)
    _normalize_exchange_details(charter_data)

    with cursor() as cur:
        _resolve_client_details(cur, charter_data)
        _resolve_vehicle_details(cur, charter_data)
        _resolve_driver_details(cur, charter_data)
        charter_data["beverages"] = _load_beverage_items(cur, charter_data)

    return _apply_pdf_field_aliases(charter_data)


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def _load_charter_pdf_data(charter_id: int) -> dict:
    """Load the richer charter data needed for the run sheet PDF."""
    with cursor() as cur:
        exchange_details_select = (
            "c.exchange_of_services_details"
            if _column_exists(cur, "charters", "exchange_of_services_details")
            else "NULL::jsonb AS exchange_of_services_details"
        )
        payment_method_select = (
            "c.payment_method"
            if _column_exists(cur, "charters", "payment_method")
            else "NULL::text AS payment_method"
        )
        payment_deleted_filter = (
            "AND deleted_at IS NULL"
            if _column_exists(cur, "payments", "deleted_at")
            else ""
        )

        cur.execute(
            f"""
            SELECT
                c.charter_id,
                c.reserve_number,
                c.client_id,
                c.charter_date,
                c.pickup_time,
                c.dropoff_time,
                c.pickup_address,
                c.dropoff_address,
                c.passenger_count,
                c.vehicle,
                c.vehicle_id,
                c.driver,
                c.employee_id,
                c.assigned_driver_id,
                c.status,
                c.charter_type,
                {exchange_details_select},
                c.total_amount_due,
                c.paid_amount,
                c.quoted_hours,
                c.actual_hours,
                c.odometer_start,
                c.odometer_end,
                c.total_kms,
                c.fuel_added,
                c.fuel_added_liters,
                c.fuel_litres,
                c.fuel_price,
                c.notes,
                c.client_notes,
                c.driver_notes,
                c.vehicle_notes,
                c.booking_notes,
                c.payment_status,
                c.amount_paid,
                {payment_method_select},
                c.driver_hours_worked,
                c.driver_hourly_rate,
                c.workshift_start,
                c.workshift_end,
                c.on_duty_started_at,
                c.off_duty_at,
                c.duty_log,
                c.cart_order_list,
                c.custom_charges,
                c.subtotal,
                c.gst_amount,
                c.grand_total,
                c.gst_exempt,
                c.charter_fee_type,
                c.hourly_rate,
                c.extra_gratuity,
                c.gratuity_percent,
                COALESCE(p.total_paid, c.amount_paid, c.paid_amount, 0) AS total_paid,
                (COALESCE(c.total_amount_due, c.grand_total, 0) - COALESCE(p.total_paid, c.amount_paid, c.paid_amount, 0)) AS balance,
                COALESCE(nrr.nrr_amount, c.nrr_amount, 0) AS nrr_amount,
                cl.client_name,
                cl.company_name,
                cl.email,
                COALESCE(cl.primary_phone, cl.phone) AS phone,
                cl.address_line1,
                cl.city,
                cl.province,
                cl.zip_code,
                v.vehicle_number,
                v.license_plate,
                v.passenger_capacity,
                COALESCE(v.description, TRIM(COALESCE(v.make, '') || ' ' || COALESCE(v.model, ''))) AS vehicle_description,
                v.vehicle_type AS vehicle_type_requested,
                CASE
                    WHEN c.locked = true AND c.cancelled = false THEN 'Reconciled'
                    WHEN c.cancelled = true THEN 'Cancelled'
                    ELSE 'Not Reconciled'
                END AS reconciliation_status
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

        record = cur.fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Charter not found")

        columns = [desc[0] for desc in cur.description]
        charter_data = dict(zip(columns, record, strict=False))
        _normalize_exchange_details(charter_data)
        _resolve_driver_details(cur, charter_data)
        _resolve_vehicle_details(cur, charter_data)
        charter_data = _apply_pdf_field_aliases(charter_data)

        reserve_number = charter_data.get("reserve_number")

        cur.execute(
            """
            SELECT
                route_sequence,
                event_type_code,
                COALESCE(
                    address, pickup_location, dropoff_location, ''
                ) AS address,
                COALESCE(stop_time, pickup_time, dropoff_time) AS stop_time,
                route_notes
            FROM charter_routes
            WHERE charter_id = %s
            ORDER BY route_sequence
            """,
            (charter_id,),
        )
        route_columns = [desc[0] for desc in cur.description]
        charter_data["routes"] = [
            dict(zip(route_columns, row, strict=False)) for row in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT charge_type, description, amount
            FROM charges
            WHERE reserve_number = %s
            ORDER BY
                CASE charge_type
                    WHEN 'base_rate' THEN 1
                    WHEN 'service_fee' THEN 2
                    WHEN 'gratuity' THEN 3
                    WHEN 'gst' THEN 4
                    WHEN 'airport_fee' THEN 5
                    ELSE 6
                END,
                charge_id
            """,
            (reserve_number,),
        )
        charge_columns = [desc[0] for desc in cur.description]
        charter_data["charges"] = [
            dict(zip(charge_columns, row, strict=False)) for row in cur.fetchall()
        ]

        if not charter_data["charges"]:
            charter_data["charges"] = _build_payload_charges(charter_data)

        cur.execute(
                        f"""
            SELECT payment_label, payment_method, amount, payment_date, notes,
            reference_number
            FROM payments
            WHERE charter_id = %s
                            {payment_deleted_filter}
            ORDER BY payment_date, payment_id
                        """,
            (charter_id,),
        )
        payment_columns = [desc[0] for desc in cur.description]
        charter_data["payments"] = [
            dict(zip(payment_columns, row, strict=False)) for row in cur.fetchall()
        ]

        charter_data["beverages"] = _load_beverage_items(cur, charter_data)

        driver_key = charter_data.get("driver") or charter_data.get("assigned_driver_id")
        charter_date = charter_data.get("charter_date")
        if driver_key and charter_date:
            cur.execute(
                """
                SELECT charter_id,
                       workshift_start,
                       on_duty_started_at,
                       duty_log,
                       pickup_time
                FROM charters
                WHERE driver = %s
                  AND charter_date = %s
                  AND charter_id < %s
                  AND (cancelled IS NULL OR cancelled = false)
                ORDER BY pickup_time ASC, charter_id ASC
                LIMIT 1
                """,
                (charter_data.get("driver"), charter_date, charter_id),
            )
            prior = cur.fetchone()
            if prior:
                pcols = [d[0] for d in cur.description]
                prior_dict = dict(zip(pcols, prior, strict=False))
                charter_data["is_second_trip"] = True
                charter_data["prior_trip_charter_id"] = prior_dict.get(
                    "charter_id"
                )
                charter_data["prior_trip_workshift_start"] = (
                    prior_dict.get("workshift_start")
                    or prior_dict.get("on_duty_started_at")
                )
                charter_data["prior_trip_duty_log"] = prior_dict.get(
                    "duty_log"
                )

    return charter_data


def _stream_pdf_response(
    pdf_bytes: bytes, filename: str, inline: bool
) -> StreamingResponse:
    disposition = "inline" if inline else "attachment"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"{disposition}; filename={filename}"},
    )


def _parse_charter_id_csv(charter_ids_csv: str) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for part in str(charter_ids_csv or "").split(","):
        value = part.strip()
        if not value:
            continue
        try:
            cid = int(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid charter ID: {value}",
            ) from exc
        if cid <= 0:
            continue
        if cid in seen:
            continue
        seen.add(cid)
        ids.append(cid)
    if not ids:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one valid charter ID",
        )
    return ids


def _generate_multi_invoice_pdf(charter_ids: list[int]) -> bytes:
    writer = PdfWriter()

    for charter_id in charter_ids:
        charter_data = _load_charter_pdf_data(charter_id)
        pdf_bytes = generate_charter_pdf(charter_data)
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _load_charter_basic_context(charter_id: int) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                COALESCE(cl.client_name, cl.company_name, '') AS client_name,
                COALESCE(c.driver, '') AS driver_name,
                COALESCE(
                    NULLIF(TRIM(COALESCE(c.vehicle, '')), ''),
                    NULLIF(TRIM(COALESCE(v.vehicle_number, '')), ''),
                    NULLIF(TRIM(COALESCE(v.license_plate, '')), ''),
                    ''
                ) AS vehicle,
                COALESCE(c.pickup_address, '') AS pickup_address,
                COALESCE(c.dropoff_address, '') AS dropoff_address
            FROM charters c
            LEFT JOIN clients cl ON cl.client_id = c.client_id
            LEFT JOIN vehicles v ON v.vehicle_id = c.vehicle_id
            WHERE c.charter_id = %s
            LIMIT 1
            """,
            (charter_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Charter not found")
        cols = [d[0] for d in (cur.description or [])]
        return dict(zip(cols, row, strict=False))


def _load_charter_beverage_snapshot(charter_id: int) -> list[dict[str, Any]]:
    with cursor() as cur:
        cur.execute(
            """
            SELECT
                item_name,
                quantity,
                unit_our_cost,
                line_cost,
                unit_price_charged,
                line_amount_charged,
                deposit_per_unit
            FROM charter_beverages
            WHERE charter_id = %s
            ORDER BY item_name
            """,
            (charter_id,),
        )
        cols = [d[0] for d in (cur.description or [])]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def _simple_lines_pdf(title: str, lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 0.75 * inch

    c.setFont("Helvetica-Bold", 14)
    c.drawString(0.75 * inch, y, title)
    y -= 0.30 * inch
    c.setFont("Helvetica", 9)

    for line in lines:
        if y < 0.75 * inch:
            c.showPage()
            y = height - 0.75 * inch
            c.setFont("Helvetica", 9)
        c.drawString(0.75 * inch, y, str(line)[:120])
        y -= 0.18 * inch

    c.save()
    buf.seek(0)
    return buf.getvalue()


@router.get("/charters/{charter_id}/invoice-pdf")
def get_charter_invoice_pdf(charter_id: int = Path(...)):
    """Generate and download charter invoice as PDF."""
    charter_data = _load_charter_pdf_data(charter_id)

    try:
        pdf_bytes = generate_charter_pdf(charter_data)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"PDF generation failed: {e!s}"
        )

    return _stream_pdf_response(
        pdf_bytes,
        f"Charter_{charter_data.get('reserve_number', 'Invoice')}.pdf",
        inline=False,
    )


@router.get("/charters/{charter_id}/invoice-pdf-preview")
def preview_charter_invoice_pdf(charter_id: int = Path(...)):
    """Preview charter invoice as PDF (inline)."""
    charter_data = _load_charter_pdf_data(charter_id)

    try:
        pdf_bytes = generate_charter_pdf(charter_data)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"PDF generation failed: {e!s}"
        )

    return _stream_pdf_response(
        pdf_bytes,
        f"Charter_{charter_data.get('reserve_number', 'Invoice')}.pdf",
        inline=True,
    )


@router.get("/charters/multi-invoice-pdf")
def get_multi_charter_invoice_pdf(
    charter_ids: Annotated[str, Query(...)],
    inline: Annotated[bool, Query()] = True,
):
    """Generate one PDF containing multiple charter invoices."""
    parsed_ids = _parse_charter_id_csv(charter_ids)

    try:
        pdf_bytes = _generate_multi_invoice_pdf(parsed_ids)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500,
            detail=f"Multi-invoice PDF generation failed: {e!s}",
        )

    filename = f"Multi_Invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return _stream_pdf_response(pdf_bytes, filename, inline=inline)


@router.get("/charters/{charter_id}/blank-run-sheet-pdf")
def get_blank_run_sheet_pdf(charter_id: int = Path(...)):
    """Generate a blank run sheet shell for manual use."""
    ctx = _load_charter_basic_context(charter_id)
    payload = {
        "charter_id": ctx.get("charter_id"),
        "reserve_number": ctx.get("reserve_number"),
        "client_name": ctx.get("client_name"),
        "charter_date": ctx.get("charter_date"),
        "vehicle": ctx.get("vehicle"),
        "driver": ctx.get("driver_name"),
        "pickup_address": ctx.get("pickup_address"),
        "dropoff_address": ctx.get("dropoff_address"),
        "routes": [],
        "charges": [],
        "payments": [],
        "quoted_hours": None,
    }
    try:
        pdf_bytes = generate_charter_pdf(payload)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Blank run sheet generation failed: {e!s}"
        )
    reserve_number = str(ctx.get("reserve_number") or charter_id)
    return _stream_pdf_response(
        pdf_bytes,
        f"Blank_Run_Sheet_{reserve_number}.pdf",
        inline=True,
    )


@router.get("/charters/{charter_id}/airport-sign-pdf")
def get_airport_sign_pdf(charter_id: int = Path(...)):
    """Generate a printable airport sign from charter context."""
    ctx = _load_charter_basic_context(charter_id)
    client_name = str(ctx.get("client_name") or "GUEST").strip() or "GUEST"
    reserve = str(ctx.get("reserve_number") or charter_id)
    lines = [
        f"RESERVE: {reserve}",
        "",
        "ARROW LIMOUSINE",
        "",
        client_name.upper(),
        "",
        f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    pdf_bytes = _simple_lines_pdf("Airport Sign", lines)
    return _stream_pdf_response(pdf_bytes, f"Airport_Sign_{reserve}.pdf", inline=True)


@router.get("/charters/{charter_id}/driver-manifest-pdf")
def get_driver_manifest_pdf(charter_id: int = Path(...)):
    """Generate driver beverage manifest with checkbox-style rows."""
    ctx = _load_charter_basic_context(charter_id)
    items = _load_charter_beverage_snapshot(charter_id)
    reserve = str(ctx.get("reserve_number") or charter_id)

    lines = [
        f"Charter ID: {charter_id}",
        f"Reserve: {reserve}",
        f"Client: {ctx.get('client_name') or ''}",
        f"Driver: {ctx.get('driver_name') or ''}",
        f"Vehicle: {ctx.get('vehicle') or ''}",
        "",
        "Driver Beverage Manifest (check items as loaded)",
        "",
    ]
    if items:
        for idx, item in enumerate(items, start=1):
            name = str(item.get("item_name") or "")
            qty = int(float(item.get("quantity") or 0))
            lines.append(f"[ ] {idx}. {name}  Qty: {qty}")
    else:
        lines.append("No beverage items found for this charter.")

    lines.extend(
        [
            "",
            "Driver Name (Print): ______________________________",
            "Driver Signature: _________________________________",
        ]
    )
    pdf_bytes = _simple_lines_pdf("Driver Manifest", lines)
    return _stream_pdf_response(pdf_bytes, f"Driver_Manifest_{reserve}.pdf", inline=True)


@router.get("/charters/{charter_id}/beverage-dispatch-pdf")
def get_beverage_dispatch_pdf(charter_id: int = Path(...)):
    """Generate internal beverage dispatch order (our costs)."""
    ctx = _load_charter_basic_context(charter_id)
    items = _load_charter_beverage_snapshot(charter_id)
    reserve = str(ctx.get("reserve_number") or charter_id)

    total_cost = 0.0
    lines = [
        f"Charter ID: {charter_id}",
        f"Reserve: {reserve}",
        f"Client: {ctx.get('client_name') or ''}",
        f"Driver: {ctx.get('driver_name') or ''}",
        f"Vehicle: {ctx.get('vehicle') or ''}",
        "",
        "Internal Dispatch Order (wholesale costs)",
        "",
    ]

    if items:
        for item in items:
            name = str(item.get("item_name") or "")
            qty = int(float(item.get("quantity") or 0))
            each = float(item.get("unit_our_cost") or 0.0)
            line_cost = float(item.get("line_cost") or (qty * each))
            total_cost += line_cost
            lines.append(f"[ ] {name} | Qty {qty} | Cost ${each:.2f} | Total ${line_cost:.2f}")
        lines.append("")
        lines.append(f"TOTAL COST TO PURCHASE: ${total_cost:.2f}")
    else:
        lines.append("No beverage items found for this charter.")

    pdf_bytes = _simple_lines_pdf("Beverage Dispatch Order", lines)
    return _stream_pdf_response(pdf_bytes, f"Dispatch_Order_{reserve}.pdf", inline=True)


@router.get("/charters/{charter_id}/beverage-guest-invoice-pdf")
def get_beverage_guest_invoice_pdf(charter_id: int = Path(...)):
    """Generate guest-facing beverage invoice from charter snapshot."""
    ctx = _load_charter_basic_context(charter_id)
    items = _load_charter_beverage_snapshot(charter_id)
    reserve = str(ctx.get("reserve_number") or charter_id)

    subtotal = 0.0
    gst_total = 0.0
    lines = [
        f"Charter ID: {charter_id}",
        f"Reserve: {reserve}",
        f"Client: {ctx.get('client_name') or ''}",
        "",
        "Guest Beverage Invoice",
        "",
    ]

    if items:
        for item in items:
            name = str(item.get("item_name") or "")
            qty = int(float(item.get("quantity") or 0))
            each = float(item.get("unit_price_charged") or 0.0)
            line_total = float(item.get("line_amount_charged") or (qty * each))
            subtotal += line_total
            gst_total += (line_total * 0.05 / 1.05) if line_total else 0.0
            lines.append(f"{name} | Qty {qty} | Price ${each:.2f} | Line ${line_total:.2f}")
        lines.append("")
        lines.append(f"Subtotal (before GST): ${subtotal - gst_total:.2f}")
        lines.append(f"GST included (5%): ${gst_total:.2f}")
        lines.append(f"TOTAL DUE: ${subtotal:.2f}")
    else:
        lines.append("No beverage items found for this charter.")

    pdf_bytes = _simple_lines_pdf("Beverage Guest Invoice", lines)
    return _stream_pdf_response(pdf_bytes, f"Beverage_Invoice_{reserve}.pdf", inline=True)


@router.get("/charters/{charter_id}/confirmation-letter-pdf")
def get_confirmation_letter_pdf(charter_id: int = Path(...)):
    """Generate client-facing confirmation letter PDF from live charter data."""
    charter_data = _load_charter_pdf_data(charter_id)

    try:
        pdf_bytes = generate_confirmation_letter_pdf(charter_data)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"PDF generation failed: {e!s}"
        )

    reserve_number = str(charter_data.get("reserve_number") or "quote")
    filename = f"Confirmation_{reserve_number}.pdf"
    return _stream_pdf_response(pdf_bytes, filename, inline=True)


@router.post("/charters/run-sheet-pdf")
def get_run_sheet_pdf_from_payload(
    payload: Annotated[dict[str, Any], Body(...)],
):
    """Generate a run charter PDF directly from the Run Charter tab payload."""
    charter_data = _build_run_sheet_payload(payload)
    try:
        pdf_bytes = generate_charter_pdf(charter_data)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"PDF generation failed: {e!s}"
        )

    filename = f"Charter_{charter_data.get('reserve_number', 'RunSheet')}.pdf"
    return _stream_pdf_response(pdf_bytes, filename, inline=False)


@router.post("/charters/run-sheet-pdf-preview")
def preview_run_sheet_pdf_from_payload(
    payload: Annotated[dict[str, Any], Body(...)],
):
    """Preview a run charter PDF directly from the Run Charter tab payload."""
    charter_data = _build_run_sheet_payload(payload)
    try:
        pdf_bytes = generate_charter_pdf(charter_data)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"PDF generation failed: {e!s}"
        )

    filename = f"Charter_{charter_data.get('reserve_number', 'RunSheet')}.pdf"
    return _stream_pdf_response(pdf_bytes, filename, inline=True)


@router.get("/employees/{employee_id}/t4-pdf/{tax_year}")
def get_employee_t4_pdf(
    employee_id: int = Path(...), tax_year: int = Path(...)
):
    """Generate and download T4 tax form for an employee"""

    with cursor() as cur:
        # Get employee information
        cur.execute(
            """
            SELECT
                employee_id,
                full_name,
                sin,
                address,
                city,
                province,
                postal_code
            FROM employees
            WHERE employee_id = %s
            """,
            (employee_id,),
        )
        employee_row = cur.fetchone()

        if not employee_row:
            raise HTTPException(
                status_code=404, detail=f"Employee {employee_id} not found"
            )

        employee_data = dict(employee_row)

        # Get T4 data from payroll
        cur.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        GREATEST(
                            COALESCE(gross_pay, 0)
                            - COALESCE(expense_reimbursement, 0),
                            0
                        )
                    ),
                    0
                ) as box14,
                COALESCE(SUM(cpp), 0) as box16,
                COALESCE(SUM(ei), 0) as box18,
                COALESCE(SUM(tax), 0) as box22,
                COALESCE(SUM(CASE WHEN ei_insurable_earnings > 0 THEN
                ei_insurable_earnings ELSE GREATEST(
                    COALESCE(gross_pay, 0) - COALESCE(expense_reimbursement, 0),
                    0
                ) END), 0) as box24,
                COALESCE(SUM(CASE WHEN cpp_pensionable_earnings > 0 THEN
                cpp_pensionable_earnings ELSE GREATEST(
                    COALESCE(gross_pay, 0) - COALESCE(expense_reimbursement, 0),
                    0
                ) END), 0) as box26,
                COALESCE(SUM(commission), 0) as box44,
                COALESCE(SUM(union_dues), 0) as box52
            FROM driver_payroll
            WHERE employee_id = %s AND year = %s
            """,
            (employee_id, tax_year),
        )
        t4_row = cur.fetchone()

        if not t4_row:
            # No payroll data - return empty T4
            t4_data = {
                "box14": 0.00,
                "box16": 0.00,
                "box18": 0.00,
                "box22": 0.00,
                "box24": 0.00,
                "box26": 0.00,
                "box44": 0.00,
                "box52": 0.00,
            }
        else:
            t4_data = dict(t4_row)

    # Generate T4 PDF
    try:
        pdf_bytes = generate_t4_pdf(employee_data, t4_data, tax_year)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"T4 PDF generation failed: {e!s}"
        )

    # Return as download
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment;"
            "filename=T4_{tax_year}_{employee_data.get('full_name',"
            "'Employee').replace(' ', '_')}.pdf"
        },
    )


@router.get("/employees/{employee_id}/t4-pdf-preview/{tax_year}")
def preview_employee_t4_pdf(
    employee_id: int = Path(...), tax_year: int = Path(...)
):
    """Preview T4 tax form for an employee (inline)"""

    with cursor() as cur:
        # Get employee information
        cur.execute(
            """
            SELECT
                employee_id,
                full_name,
                sin,
                address,
                city,
                province,
                postal_code
            FROM employees
            WHERE employee_id = %s
            """,
            (employee_id,),
        )
        employee_row = cur.fetchone()

        if not employee_row:
            raise HTTPException(
                status_code=404, detail=f"Employee {employee_id} not found"
            )

        employee_data = dict(employee_row)

        # Get T4 data from payroll
        cur.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        GREATEST(
                            COALESCE(gross_pay, 0)
                            - COALESCE(expense_reimbursement, 0),
                            0
                        )
                    ),
                    0
                ) as box14,
                COALESCE(SUM(cpp), 0) as box16,
                COALESCE(SUM(ei), 0) as box18,
                COALESCE(SUM(tax), 0) as box22,
                COALESCE(SUM(CASE WHEN ei_insurable_earnings > 0 THEN
                ei_insurable_earnings ELSE GREATEST(
                    COALESCE(gross_pay, 0) - COALESCE(expense_reimbursement, 0),
                    0
                ) END), 0) as box24,
                COALESCE(SUM(CASE WHEN cpp_pensionable_earnings > 0 THEN
                cpp_pensionable_earnings ELSE GREATEST(
                    COALESCE(gross_pay, 0) - COALESCE(expense_reimbursement, 0),
                    0
                ) END), 0) as box26,
                COALESCE(SUM(commission), 0) as box44,
                COALESCE(SUM(union_dues), 0) as box52
            FROM driver_payroll
            WHERE employee_id = %s AND year = %s
            """,
            (employee_id, tax_year),
        )
        t4_row = cur.fetchone()

        if not t4_row:
            t4_data = {
                "box14": 0.00,
                "box16": 0.00,
                "box18": 0.00,
                "box22": 0.00,
                "box24": 0.00,
                "box26": 0.00,
                "box44": 0.00,
                "box52": 0.00,
            }
        else:
            t4_data = dict(t4_row)

    # Generate T4 PDF
    try:
        pdf_bytes = generate_t4_pdf(employee_data, t4_data, tax_year)
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"T4 PDF generation failed: {e!s}"
        )

    # Return as inline display
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf")
