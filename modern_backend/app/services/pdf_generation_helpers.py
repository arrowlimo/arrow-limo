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
    "Starting at: {{pickup_time}}    Predicted End Time: {{dropoff_time}}\n\n"
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
    return _render_confirmation_template_text(template, charter_data)


def _format_confirmation_date(value: Any) -> str:
    if not value:
        return ""
    try:
        parsed = value
        if not hasattr(parsed, "strftime"):
            parsed = datetime.fromisoformat(str(value)[:10])
        return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
    except (TypeError, ValueError):
        return str(value)


def _format_confirmation_time(value: Any) -> str:
    if not value:
        return ""
    try:
        parsed = value
        if not hasattr(parsed, "strftime"):
            raw = str(value).strip()
            parsed = datetime.strptime(raw[:8], "%H:%M:%S" if raw.count(":") >= 2 else "%H:%M")
        return parsed.strftime("%I:%M %p").lstrip("0")
    except (TypeError, ValueError):
        return str(value)


def _render_confirmation_template_text(
    template: str,
    charter_data: dict[str, Any],
) -> str:

    def _value(*keys: str) -> str:
        for key in keys:
            if key in charter_data and charter_data.get(key) not in (None, ""):
                return str(charter_data.get(key))
        return ""

    client_name = _value("client_display_name", "client_name", "company_name")
    reserve_number = _value("reservation_number", "reserve_number", "charter_id")
    charter_date = _format_confirmation_date(_value("charter_date"))
    pickup_time = _format_confirmation_time(_value("pickup_time", "actual_pickup_time"))
    dropoff_time = _format_confirmation_time(_value("dropoff_time", "actual_dropoff_time"))
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
                normalized_addr = str(addr).strip()
                narrative = normalized_addr.lower().startswith(
                    ("leave ", "arrive ", "return ", "depart ")
                )
                piece = normalized_addr if narrative else f"{event_type}: {normalized_addr}"
                if stop_time:
                    piece += f" @ {_format_confirmation_time(stop_time)}"
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


def _render_confirmation_template_sections(
    charter_data: dict[str, Any],
) -> tuple[str, str]:
    """Return editable prose around the generator-owned reservation details."""
    template = _normalize_template_text(_load_active_confirmation_template())
    blocks = [block.strip() for block in re.split(r"\n\s*\n", template) if block.strip()]
    intro_blocks: list[str] = []
    closing_blocks: list[str] = []
    reached_details = False
    reached_itinerary = False
    detail_tokens = (
        "{{charter_date}}",
        "{{pickup_time}}",
        "{{dropoff_time}}",
        "{{vehicle_type}}",
    )

    for index, block in enumerate(blocks):
        if index == 0 and block.lower().startswith("dear "):
            continue
        if "{{itinerary}}" in block:
            reached_details = True
            reached_itinerary = True
            continue
        if any(token in block for token in detail_tokens):
            reached_details = True
            continue
        if reached_itinerary:
            closing_blocks.append(block)
        elif not reached_details:
            intro_blocks.append(block)

    intro = _render_confirmation_template_text("\n\n".join(intro_blocks), charter_data)
    closing = _render_confirmation_template_text("\n\n".join(closing_blocks), charter_data)
    return intro, closing


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
        sections: list[tuple[str, str]] = []
        current_heading = ""
        current_body: list[str] = []
        in_policies = False
        known_normal_headings = {
            "Alcohol Regulations",
            "Safe driving policy",
        }

        def flush() -> None:
            nonlocal current_heading, current_body
            if current_heading:
                sections.append((current_heading, "\n".join(current_body).strip()))
            current_heading = ""
            current_body = []

        for paragraph in document.paragraphs:
            text = (paragraph.text or "").strip()
            if not text:
                continue
            if text == "Policies & Terms":
                in_policies = True
                continue
            if not in_policies:
                continue
            if text.startswith("We appreciate your business."):
                break

            if text.endswith(" Out-of-Town Charters"):
                body_text = text[: -len(" Out-of-Town Charters")].strip()
                if body_text:
                    current_body.append(body_text)
                flush()
                current_heading = "Out-of-Town Charters"
                continue

            style_name = (getattr(paragraph.style, "name", "") or "").strip()
            is_heading = style_name.startswith("Heading") or text in known_normal_headings
            if is_heading:
                flush()
                current_heading = text
            elif current_heading:
                current_body.append(text)
        flush()
        return sections
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
