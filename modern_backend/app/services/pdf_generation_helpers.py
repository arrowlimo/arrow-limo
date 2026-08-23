import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..db import cursor

SERVICE_FEE_LABEL = "Service Fee"
UTC_OFFSET_SUFFIX = "+00:00"
DEFAULT_CONFIRMATION_TEMPLATE = (
    "Dear {{client_name}}:\n\n"
    "Thank you for choosing Arrow Limousine & Sedan Services Ltd. "
    "We have reserved the following transportation for you.\n\n"
    "Date for the Reservation: {{charter_date}}    "
    "Arrival Time: {{pickup_time}}    Predicted End Time: {{dropoff_time}}\n\n"
    "Type of Vehicle: {{vehicle_type}}\n\n"
    "Itinerary:\n{{itinerary}}\n\n"
    "Please review the details above and contact our office with any questions. "
    "We look forward to serving you."
)
DEFAULT_QUOTE_TEMPLATE = (
    "Dear {{client_name}},\n\n"
    "Thank you for requesting a quote from Arrow Limousine & Sedan Services Ltd. "
    "We are pleased to provide the following transportation estimate for your reservation. "
    "Quote Number: {{quote_number}}. Request date: {{charter_date}}. "
    "Vehicle type: {{vehicle_type}}. Pickup / dropoff: {{pickup_time}} to {{dropoff_time}}.\n\n"
    "Please review the itinerary and rates below. We would be happy to confirm the booking "
    "once you are ready to proceed."
)


def _normalize_template_text(raw_text: str | None) -> str:
    if raw_text is None:
        return ""
    text = str(raw_text)
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("</p>", "\n\n").replace("</div>", "\n\n")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"<li[^>]*>", "\n• ", text, flags=re.IGNORECASE)
    text = text.replace("</li>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ensure_confirmation_letter_template_table() -> None:
    with cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS confirmation_letter_templates (
                template_id SERIAL PRIMARY KEY,
                name VARCHAR(120) NOT NULL DEFAULT 'default',
                subject VARCHAR(255) NOT NULL DEFAULT 'Confirmation Letter',
                body TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            INSERT INTO confirmation_letter_templates (name, subject, body, is_active)
            SELECT %s, %s, %s, TRUE
            WHERE NOT EXISTS (
                SELECT 1
                FROM confirmation_letter_templates
                WHERE name = %s
            )
            """,
            ("default", "Confirmation Letter", DEFAULT_CONFIRMATION_TEMPLATE, "default"),
        )


def _load_active_confirmation_template() -> str:
    try:
        _ensure_confirmation_letter_template_table()
        with cursor() as cur:
            cur.execute(
                """
                SELECT body
                FROM confirmation_letter_templates
                WHERE is_active = TRUE
                ORDER BY updated_at DESC, template_id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return DEFAULT_CONFIRMATION_TEMPLATE


def _ensure_quote_letter_template_table() -> None:
    with cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS quote_letter_templates (
                template_id SERIAL PRIMARY KEY,
                name VARCHAR(120) NOT NULL DEFAULT 'default',
                subject VARCHAR(255) NOT NULL DEFAULT 'Quote Letter',
                body TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            INSERT INTO quote_letter_templates (name, subject, body, is_active)
            SELECT %s, %s, %s, TRUE
            WHERE NOT EXISTS (
                SELECT 1
                FROM quote_letter_templates
                WHERE name = %s
            )
            """,
            ("default", "Quote Letter", DEFAULT_QUOTE_TEMPLATE, "default"),
        )


def _load_active_quote_template() -> str:
    try:
        _ensure_quote_letter_template_table()
        with cursor() as cur:
            cur.execute(
                """
                SELECT body
                FROM quote_letter_templates
                WHERE is_active = TRUE
                ORDER BY updated_at DESC, template_id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return DEFAULT_QUOTE_TEMPLATE


def _render_confirmation_template_body(charter_data: dict[str, Any] | None) -> str:
    template = _normalize_template_text(_load_active_confirmation_template())
    if not charter_data:
        return template

    def _value(*keys: str) -> str:
        for key in keys:
            if key in charter_data and charter_data.get(key) not in (None, ""):
                return str(charter_data.get(key))
        return ""

    client_name = _value("client_name", "client_display_name", "company_name")
    reserve_number = _value("reservation_number", "reserve_number", "charter_id")
    charter_date = _value("charter_date")
    pickup_time = _value("pickup_time", "actual_pickup_time")
    dropoff_time = _value("dropoff_time", "actual_dropoff_time")
    vehicle = _value(
        "vehicle_type",
        "requested_vehicle_type",
        "vehicle_type_requested",
        "vehicle",
        "vehicle_description",
    )
    driver = _value("driver_name", "assigned_driver", "driver", "driver_display_name")
    itinerary = _value("itinerary", "itinerary_summary")
    if not itinerary:
        routes = charter_data.get("routes") or []
        parts = []
        for route in routes:
            addr = route.get("address") or route.get("pickup_location") or route.get("dropoff_location") or ""
            stop_time = route.get("stop_time") or route.get("pickup_time") or route.get("dropoff_time") or ""
            event_type = route.get("event_type_label") or route.get("event_type_code") or "Stop"
            if addr:
                piece = f"{event_type}: {addr}"
                if stop_time:
                    piece += f" @ {stop_time}"
                parts.append(piece)
        itinerary = "\n".join(parts)

    rendered = template
    replacements = {
        "client_name": client_name or "Client",
        "reservation_number": reserve_number or "TBD",
        "quote_number": reserve_number or "TBD",
        "charter_date": charter_date or "TBD",
        "pickup_time": pickup_time or "TBD",
        "dropoff_time": dropoff_time or "TBD",
        "vehicle_type": vehicle or "TBD",
        "driver_name": driver or "",
        "itinerary": itinerary or "No itinerary details entered.",
    }
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value).strip())
    return rendered.strip()


def _render_quote_template_body(charter_data: dict[str, Any] | None) -> str:
    template = _normalize_template_text(_load_active_quote_template())
    if not charter_data:
        return template

    def _value(*keys: str) -> str:
        for key in keys:
            if key in charter_data and charter_data.get(key) not in (None, ""):
                return str(charter_data.get(key))
        return ""

    client_name = _value("client_name", "client_display_name", "company_name")
    quote_number = _value("quote_number", "reservation_number", "reserve_number", "charter_id")
    charter_date = _value("charter_date")
    pickup_time = _value("pickup_time", "actual_pickup_time")
    dropoff_time = _value("dropoff_time", "actual_dropoff_time")
    vehicle = _value(
        "vehicle_type_requested",
        "vehicle_type",
        "vehicle",
        "vehicle_description",
        "requested_vehicle_type",
    )
    itinerary = _value("itinerary", "quote_itinerary_lines")
    quote_lines = charter_data.get("quote_itinerary_lines")
    if not itinerary and isinstance(quote_lines, (list, tuple)):
        itinerary = "\n".join(str(item) for item in quote_lines if item)
    if not itinerary:
        route_rows = charter_data.get("routes")
        if isinstance(route_rows, (list, tuple)):
            itinerary = "; ".join(
                str(
                    route.get("address")
                    or route.get("pickup_location")
                    or route.get("dropoff_location")
                    or ""
                )
                for route in route_rows
                if isinstance(route, dict)
            )

    replacements = {
        "client_name": client_name or "Client",
        "quote_number": quote_number or "QUOTE",
        "reservation_number": quote_number or "QUOTE",
        "charter_date": charter_date or "TBD",
        "pickup_time": pickup_time or "TBD",
        "dropoff_time": dropoff_time or "TBD",
        "vehicle_type": vehicle or "TBD",
        "itinerary": itinerary or "No itinerary details entered.",
    }
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value).strip())
    return rendered.strip()


def _load_docx_policy_sections() -> list[tuple[str, str]]:
    try:
        from docx import Document

        root = Path(__file__).resolve().parents[3]
        template_path = root / "forms" / "templates" / "confirmationletter.docx"
        document = Document(str(template_path))
        paragraphs = [p.text.strip() for p in document.paragraphs]
        start = next(
            (i for i, text in enumerate(paragraphs) if text.lower() == "policies & terms"),
            None,
        )
        if start is None:
            return []

        sections: list[tuple[str, list[str]]] = []
        current_heading = ""
        current_body: list[str] = []
        heading_pattern = re.compile(r"^(?:\d+\.\s+|non-refundable retainer)", re.IGNORECASE)
        for text in paragraphs[start + 1 :]:
            if not text:
                continue
            if text.lower().startswith("sincerely"):
                break
            if heading_pattern.match(text):
                if current_heading:
                    sections.append((current_heading, current_body))
                current_heading = text
                current_body = []
            elif current_heading:
                current_body.append(text)
        if current_heading:
            sections.append((current_heading, current_body))
        return [(heading, "\n".join(body)) for heading, body in sections]
    except Exception:
        return []


def _parse_route_sort_minutes(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def _sorted_routes_for_itinerary(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        routes or [],
        key=lambda route: (
            _parse_route_sort_minutes(
                route.get("route_sequence")
                or route.get("stop_sequence")
                or route.get("sort_order")
                or route.get("stop_time")
            )
            or 99999,
            str(route.get("event_type_code") or route.get("event_type_label") or ""),
        ),
    )


def _safe_text(v: Any, default: str = "") -> str:
    if v is None:
        return default
    if isinstance(v, str):
        return v
    return str(v)


def _fmt_date_mmddyyyy(v: Any) -> str:
    txt = _safe_text(v, "")
    if not txt:
        return ""
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00")).strftime("%m/%d/%Y")
    except Exception:
        return txt


def _fmt_time_12h(v: Any) -> str:
    txt = _safe_text(v, "")
    if not txt:
        return ""
    try:
        dt = datetime.fromisoformat(txt.replace("Z", "+00:00"))
        return dt.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return txt


def _fmt_money(v: Any) -> str:
    try:
        return f"${float(v or 0):,.2f}"
    except Exception:
        return "$0.00"


def _is_cancelled_charter(charter_data: dict[str, Any] | None) -> bool:
    if not charter_data:
        return False
    status = str(charter_data.get("status") or "").strip().lower()
    return status in {"cancelled", "canceled", "void", "deleted"}


def _build_confirmation_template_values(charter_data: dict[str, Any]) -> dict[str, str]:
    routes = _sorted_routes_for_itinerary(list(charter_data.get("routes") or []))
    itinerary_lines = []
    for route in routes:
        pieces = [
            _safe_text(route.get("event_type_label") or route.get("event_type_code")),
            _safe_text(route.get("address") or route.get("pickup_location") or route.get("dropoff_location")),
            _safe_text(route.get("stop_time") or route.get("pickup_time") or route.get("dropoff_time")),
        ]
        itinerary_lines.append(" - ".join(part for part in pieces if part))

    return {
        "client_name": _safe_text(
            charter_data.get("client_name")
            or charter_data.get("client_display_name")
            or charter_data.get("company_name"),
            "Client",
        ),
        "charter_date": _fmt_date_mmddyyyy(charter_data.get("charter_date")),
        "pickup_time": _fmt_time_12h(charter_data.get("pickup_time") or charter_data.get("actual_pickup_time")),
        "dropoff_time": _fmt_time_12h(charter_data.get("dropoff_time") or charter_data.get("actual_dropoff_time")),
        "vehicle_type": _safe_text(
            charter_data.get("vehicle_type")
            or charter_data.get("vehicle_type_requested")
            or charter_data.get("vehicle_description")
            or charter_data.get("requested_vehicle_type"),
            "TBD",
        ),
        "itinerary": "\n".join(itinerary_lines).strip(),
    }


def _generate_confirmation_from_template(charter_data: dict[str, Any]) -> str:
    template = _render_confirmation_template_body(charter_data)
    values = _build_confirmation_template_values(charter_data)
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered.strip()
