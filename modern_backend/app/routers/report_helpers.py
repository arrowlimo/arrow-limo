import csv
import io
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..audit.schemas import AuditEventActor


class AccountingRuleUpsert(BaseModel):
    rule_name: str = Field(min_length=2, max_length=120)
    match_field: str = Field(min_length=2, max_length=64)
    match_pattern: str = Field(min_length=1, max_length=255)
    gl_code: str = Field(min_length=1, max_length=32)
    account_type: str | None = Field(default=None, max_length=64)
    sort_order: int = Field(default=100, ge=0, le=10000)
    is_active: bool = True


class ReceiptGLReclassifyRequest(BaseModel):
    receipt_ids: list[int] = Field(min_length=1)
    gl_code: str = Field(min_length=1, max_length=32)


class LedgerReclassifyRequest(BaseModel):
    ledger_ids: list[int] = Field(min_length=1)
    gl_code: str | None = Field(default=None, max_length=32)
    account_name: str | None = Field(default=None, max_length=255)
    account_type: str | None = Field(default=None, max_length=64)


def _ensure_accounting_rules_table(conn) -> None:
    """Create accounting rules table lazily so CRUD endpoints are usable."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS accounting_gl_rules (
                rule_id SERIAL PRIMARY KEY,
                rule_name TEXT UNIQUE NOT NULL,
                match_field TEXT NOT NULL,
                match_pattern TEXT NOT NULL,
                gl_code TEXT NOT NULL,
                account_type TEXT NULL,
                sort_order INTEGER NOT NULL DEFAULT 100,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_accounting_gl_rules_sort
            ON accounting_gl_rules (is_active, sort_order, rule_id)
            """
        )
    conn.commit()


def _validate_rule_field(match_field: str) -> None:
    allowed = {
        "name",
        "memo_description",
        "account_name",
        "supplier",
        "customer",
        "employee",
        "transaction_type",
    }
    if match_field not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_match_field", "allowed": sorted(allowed)},
        )


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


def _load_rule_snapshot(conn, rule_id: int) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rule_id, rule_name, match_field, match_pattern,
                   gl_code, account_type, sort_order, is_active,
                   created_at, updated_at
            FROM accounting_gl_rules
            WHERE rule_id = %s
            """,
            (rule_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "rule_id": int(row[0]),
        "rule_name": row[1],
        "match_field": row[2],
        "match_pattern": row[3],
        "gl_code": row[4],
        "account_type": row[5],
        "sort_order": int(row[6] or 0),
        "is_active": bool(row[7]),
        "created_at": row[8].isoformat() if hasattr(row[8], "isoformat") else None,
        "updated_at": row[9].isoformat() if hasattr(row[9], "isoformat") else None,
    }


def _write_cursor_rows_to_csv(cur, writer: Any, chunk_size: int = 5000) -> int:
    """Write cursor rows in chunks to avoid loading entire result sets."""
    total_rows = 0
    while True:
        batch = cur.fetchmany(chunk_size)
        if not batch:
            break
        writer.writerows(batch)
        total_rows += len(batch)
    return total_rows


def _parse_iso_date(value: str | None, fallback: datetime | None = None) -> datetime | None:
    """Safe ISO date parser with optional fallback."""
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid_date_format") from exc


def _has_column(conn, table: str, column: str) -> bool:
    """Check if a column exists before building dynamic queries."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table, column),
        )
        return cur.fetchone() is not None


def _first_existing_column(conn, table: str, candidates: list[str]) -> str | None:
    """Return first existing column name from candidates, else None."""
    for col in candidates:
        if _has_column(conn, table, col):
            return col
    return None


def _charter_text_expr(col_name: str | None, fallback: str = "") -> str:
    if col_name:
        return f"COALESCE(c.{col_name}::text, '')"
    return f"'{fallback}'"


def _charter_numeric_expr(col_name: str | None, fallback: str = "0") -> str:
    if col_name:
        return f"COALESCE(c.{col_name}::numeric, {fallback})"
    return fallback


def _build_legacy_ops_select(conn) -> tuple[str, str | None]:
    """Build a schema-tolerant SELECT for legacy ops style report rows."""
    reserve_col = _first_existing_column(
        conn, "charters", ["reserve_number", "reserve_no", "order_number"]
    )
    date_col = _first_existing_column(
        conn,
        "charters",
        ["pickup_date", "charter_date", "order_date", "created_at"],
    )
    amount_col = _first_existing_column(
        conn,
        "charters",
        ["total_amount_due", "amount", "total", "quoted_amount"],
    )
    paid_col = _first_existing_column(conn, "charters", ["paid_amount", "total_paid"])

    destination_col = _first_existing_column(
        conn,
        "charters",
        ["dropoff_address", "destination"],
    )
    passenger_col = _first_existing_column(
        conn,
        "charters",
        ["client_display_name", "passenger_name", "client_name"],
    )
    bill_to_col = _first_existing_column(
        conn,
        "charters",
        ["bill_to", "client_display_name", "client_name"],
    )
    account_number_col = _first_existing_column(conn, "charters", ["account_number"])
    account_type_col = _first_existing_column(conn, "charters", ["account_type"])
    agency_number_col = _first_existing_column(conn, "charters", ["agency_number"])
    payment_type_col = _first_existing_column(conn, "charters", ["payment_type", "payment_method"])
    profit_center_col = _first_existing_column(conn, "charters", ["profit_center"])
    driver_col = _first_existing_column(conn, "charters", ["driver_name", "driver"])
    vehicle_col = _first_existing_column(conn, "charters", ["vehicle", "vehicle_number"])
    vehicle_type_col = _first_existing_column(
        conn,
        "charters",
        ["vehicle_type_requested", "vehicle_type", "vehicle_description"],
    )
    run_type_col = _first_existing_column(conn, "charters", ["run_type", "charter_type"])
    status_col = _first_existing_column(conn, "charters", ["status"])
    sales_person_col = _first_existing_column(
        conn,
        "charters",
        ["sales_person", "taken_by", "booked_by", "created_by"],
    )
    taken_by_col = _first_existing_column(conn, "charters", ["taken_by", "booked_by", "created_by"])
    group_number_col = _first_existing_column(conn, "charters", ["group_number", "group_no"])
    _date_expr = f"c.{date_col}::date" if date_col else "NULL::date"

    select_sql = f"""
        SELECT
            {_charter_text_expr(reserve_col)} AS order_number,
            {_date_expr} AS order_date,
            {_charter_text_expr(destination_col)} AS destination,
            {_charter_text_expr(passenger_col)} AS passenger_name,
            {_charter_text_expr(bill_to_col)} AS bill_to,
            {_charter_text_expr(account_number_col)} AS account_number,
            {_charter_text_expr(account_type_col)} AS account_type,
            {_charter_text_expr(agency_number_col)} AS agency_number,
            {_charter_text_expr(payment_type_col)} AS payment_type,
            {_charter_text_expr(profit_center_col)} AS profit_center,
            {_charter_text_expr(driver_col)} AS driver,
            {_charter_text_expr(vehicle_col)} AS vehicle,
            {_charter_text_expr(vehicle_type_col)} AS vehicle_type,
            {_charter_text_expr(run_type_col)} AS run_type,
            {_charter_text_expr(status_col)} AS status,
            {_charter_text_expr(sales_person_col)} AS sales_person,
            {_charter_text_expr(taken_by_col)} AS taken_by,
            {_charter_text_expr(group_number_col)} AS group_number,
            {_charter_numeric_expr(amount_col)} AS amount,
            {_charter_numeric_expr(paid_col)} AS paid_amount,
            ({_charter_numeric_expr(amount_col)}
             - {_charter_numeric_expr(paid_col)}) AS balance
        FROM charters c
    """

    return select_sql, date_col


def _to_csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    headers = [] if not rows else list(rows[0].keys())
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if headers:
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(h, "") for h in headers])
    data = buffer.getvalue()
    buffer.close()
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
