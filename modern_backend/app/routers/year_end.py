from datetime import date, datetime
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/year-end", tags=["year_end_close"])


class YearEndChecklistItem(BaseModel):
    item_id: int = Field(ge=1, le=1000)
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=500)
    completed: bool = False


class YearEndCloseRequest(BaseModel):
    fiscal_year: int = Field(ge=2000, le=2100)
    force: bool = False
    notes: str | None = Field(default=None, max_length=1000)


def _ensure_tables(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS year_end_closes (
                close_id SERIAL PRIMARY KEY,
                fiscal_year INTEGER UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'closed',
                total_revenue NUMERIC NOT NULL DEFAULT 0,
                total_expenses NUMERIC NOT NULL DEFAULT 0,
                net_income NUMERIC NOT NULL DEFAULT 0,
                retained_earnings_rollover NUMERIC NOT NULL DEFAULT 0,
                capital_gains NUMERIC NOT NULL DEFAULT 0,
                notes TEXT,
                executed_by TEXT,
                closed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                summary_json JSONB
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS year_end_checklist (
                fiscal_year INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (fiscal_year, item_id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS year_end_rollovers (
                rollover_id SERIAL PRIMARY KEY,
                fiscal_year INTEGER NOT NULL,
                account_code TEXT,
                account_name TEXT,
                amount NUMERIC NOT NULL,
                direction TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                metadata JSONB
            )
            """
        )
    conn.commit()


def _has_column(conn, table: str, column: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table, column),
        )
        return cur.fetchone() is not None


def _date_bounds(fiscal_year: int) -> tuple[date, date]:
    return date(fiscal_year, 1, 1), date(fiscal_year, 12, 31)


def _compute_summary(conn, fiscal_year: int) -> dict[str, float]:
    start_date, end_date = _date_bounds(fiscal_year)

    charter_date_col = (
        "charter_date"
        if _has_column(conn, "charters", "charter_date")
        else "pickup_date"
        if _has_column(conn, "charters", "pickup_date")
        else None
    )
    revenue_col = (
        "grand_total"
        if _has_column(conn, "charters", "grand_total")
        else "total_amount_due"
        if _has_column(conn, "charters", "total_amount_due")
        else None
    )

    total_revenue = 0.0
    if charter_date_col and revenue_col:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM({revenue_col}), 0)
                FROM charters
                WHERE {charter_date_col} BETWEEN %s AND %s
                """,
                (start_date, end_date),
            )
            total_revenue = float(cur.fetchone()[0] or 0.0)

    receipt_date_col = (
        "receipt_date"
        if _has_column(conn, "receipts", "receipt_date")
        else "date"
        if _has_column(conn, "receipts", "date")
        else None
    )
    expense_col = (
        "gross_amount"
        if _has_column(conn, "receipts", "gross_amount")
        else "amount"
        if _has_column(conn, "receipts", "amount")
        else None
    )

    total_expenses = 0.0
    if receipt_date_col and expense_col:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COALESCE(SUM({expense_col}), 0)
                FROM receipts
                WHERE {receipt_date_col} BETWEEN %s AND %s
                """,
                (start_date, end_date),
            )
            total_expenses = float(cur.fetchone()[0] or 0.0)

    net_income = total_revenue - total_expenses
    return {
        "total_revenue": round(total_revenue, 2),
        "total_expenses": round(total_expenses, 2),
        "net_income": round(net_income, 2),
    }


def _compute_capital_gains(conn, fiscal_year: int) -> dict[str, Any]:
    start_date, end_date = _date_bounds(fiscal_year)

    total = 0.0
    items: list[dict[str, Any]] = []

    if _has_column(conn, "fixed_assets", "sold_date") and _has_column(
        conn, "fixed_assets", "sale_price"
    ) and _has_column(conn, "fixed_assets", "cost_basis"):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT asset_id, sold_date, sale_price, cost_basis,
                       (COALESCE(sale_price, 0) - COALESCE(cost_basis, 0)) AS gain
                FROM fixed_assets
                WHERE sold_date BETWEEN %s AND %s
                """,
                (start_date, end_date),
            )
            rows = cur.fetchall()
        for r in rows:
            gain = float(r[4] or 0.0)
            total += gain
            items.append(
                {
                    "source": "fixed_assets",
                    "asset_id": r[0],
                    "date": str(r[1]),
                    "sale_price": float(r[2] or 0.0),
                    "cost_basis": float(r[3] or 0.0),
                    "gain": round(gain, 2),
                }
            )
        return {"capital_gains": round(total, 2), "items": items}

    # Fallback on general ledger signal words.
    if _has_column(conn, "general_ledger", "date") and _has_column(
        conn, "general_ledger", "credit"
    ) and _has_column(conn, "general_ledger", "debit"):
        memo_col = (
            "memo_description"
            if _has_column(conn, "general_ledger", "memo_description")
            else None
        )
        acct_name_col = (
            "account_name"
            if _has_column(conn, "general_ledger", "account_name")
            else None
        )
        name_col = "name" if _has_column(conn, "general_ledger", "name") else None

        predicates = []
        if memo_col:
            predicates.append(f"{memo_col} ILIKE '%%capital gain%%'")
        if acct_name_col:
            predicates.append(f"{acct_name_col} ILIKE '%%capital gain%%'")
        if name_col:
            predicates.append(f"{name_col} ILIKE '%%capital gain%%'")

        if predicates:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, date,
                           COALESCE(credit, 0) - COALESCE(debit, 0) AS gain,
                           COALESCE(account_name, '')
                    FROM general_ledger
                    WHERE date BETWEEN %s AND %s
                      AND ({' OR '.join(predicates)})
                    ORDER BY date, id
                    LIMIT 500
                    """,
                    (start_date, end_date),
                )
                rows = cur.fetchall()
            for r in rows:
                gain = float(r[2] or 0.0)
                total += gain
                items.append(
                    {
                        "source": "general_ledger",
                        "id": r[0],
                        "date": str(r[1]),
                        "gain": round(gain, 2),
                        "account_name": r[3],
                    }
                )

    return {"capital_gains": round(total, 2), "items": items}


def _get_checklist(conn, fiscal_year: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT item_id, title, COALESCE(description, ''), completed, updated_at
            FROM year_end_checklist
            WHERE fiscal_year = %s
            ORDER BY item_id
            """,
            (fiscal_year,),
        )
        rows = cur.fetchall()

    return [
        {
            "item_id": r[0],
            "title": r[1],
            "description": r[2],
            "completed": bool(r[3]),
            "updated_at": r[4].isoformat() if hasattr(r[4], "isoformat") else None,
        }
        for r in rows
    ]


def _checklist_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    completed = sum(1 for i in items if i.get("completed"))
    return {
        "total": total,
        "completed": completed,
        "all_complete": total > 0 and completed == total,
    }


def _insert_rollover_marker(conn, fiscal_year: int, net_income: float) -> dict[str, Any]:
    direction = "credit" if net_income >= 0 else "debit"
    amount = abs(net_income)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO year_end_rollovers (
                fiscal_year, account_code, account_name,
                amount, direction, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING rollover_id, created_at
            """,
            (
                fiscal_year,
                "3000",
                "Retained Earnings",
                amount,
                direction,
                '{"source":"year_end_close"}',
            ),
        )
        row = cur.fetchone()

    # Best-effort mirror entry in general_ledger if schema supports it.
    required_cols = [
        _has_column(conn, "general_ledger", "date"),
        _has_column(conn, "general_ledger", "transaction_type"),
        _has_column(conn, "general_ledger", "account"),
        _has_column(conn, "general_ledger", "account_name"),
        _has_column(conn, "general_ledger", "debit"),
        _has_column(conn, "general_ledger", "credit"),
    ]
    if all(required_cols):
        debit_val = amount if direction == "debit" else 0.0
        credit_val = amount if direction == "credit" else 0.0
        cols = ["date", "transaction_type", "account", "account_name", "debit", "credit"]
        vals = [datetime(fiscal_year, 12, 31).date(), "year_end_rollover", "3000", "Retained Earnings", debit_val, credit_val]

        optional = {
            "num": f"YE-{fiscal_year}",
            "name": f"Year-End Close {fiscal_year}",
            "memo_description": "Automated retained earnings rollover",
            "account_full_name": "Equity:Retained Earnings",
        }
        for col, value in optional.items():
            if _has_column(conn, "general_ledger", col):
                cols.append(col)
                vals.append(value)

        placeholders = ", ".join(["%s"] * len(vals))
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO general_ledger ({', '.join(cols)}) VALUES ({placeholders})",
                vals,
            )

    return {
        "rollover_id": row[0],
        "created_at": row[1].isoformat() if hasattr(row[1], "isoformat") else None,
        "direction": direction,
        "amount": round(amount, 2),
    }


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "") or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


@router.get("/summary/{fiscal_year}")
def get_year_end_summary(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        return {
            "fiscal_year": fiscal_year,
            **_compute_summary(conn, fiscal_year),
        }
    finally:
        conn.close()


@router.get("/capital-gains/{fiscal_year}")
def get_capital_gains(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        data = _compute_capital_gains(conn, fiscal_year)
        return {"fiscal_year": fiscal_year, **data}
    finally:
        conn.close()


@router.get("/checklist/{fiscal_year}")
def get_year_end_checklist(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        items = _get_checklist(conn, fiscal_year)
        return {
            "fiscal_year": fiscal_year,
            "items": items,
            "summary": _checklist_summary(items),
        }
    finally:
        conn.close()


@router.post("/checklist/{fiscal_year}")
def upsert_year_end_checklist_item(fiscal_year: int, item: YearEndChecklistItem):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO year_end_checklist (
                    fiscal_year, item_id, title, description, completed, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (fiscal_year, item_id)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    completed = EXCLUDED.completed,
                    updated_at = NOW()
                """,
                (
                    fiscal_year,
                    item.item_id,
                    item.title.strip(),
                    item.description.strip(),
                    item.completed,
                ),
            )
        conn.commit()
        return {"status": "saved", "fiscal_year": fiscal_year, "item_id": item.item_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"failed_to_save_checklist_item: {exc}") from exc
    finally:
        conn.close()


@router.get("/status/{fiscal_year}")
def get_year_end_status(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        summary = _compute_summary(conn, fiscal_year)
        gains = _compute_capital_gains(conn, fiscal_year)
        checklist_items = _get_checklist(conn, fiscal_year)
        checklist = _checklist_summary(checklist_items)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT close_id, closed_at, total_revenue, total_expenses,
                       net_income, retained_earnings_rollover, capital_gains
                FROM year_end_closes
                WHERE fiscal_year = %s
                """,
                (fiscal_year,),
            )
            row = cur.fetchone()

        if row:
            return {
                "fiscal_year": fiscal_year,
                "status": "closed",
                "message": f"Fiscal year {fiscal_year} is closed.",
                "summary": {
                    "total_revenue": float(row[2] or 0.0),
                    "total_expenses": float(row[3] or 0.0),
                    "net_income": float(row[4] or 0.0),
                    "retained_earnings_rollover": float(row[5] or 0.0),
                    "capital_gains": float(row[6] or 0.0),
                    "closed_at": row[1].isoformat() if hasattr(row[1], "isoformat") else None,
                },
                "checklist": checklist,
            }

        return {
            "fiscal_year": fiscal_year,
            "status": "open",
            "message": f"Fiscal year {fiscal_year} is open.",
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
                "closed_at": None,
            },
            "checklist": checklist,
        }
    finally:
        conn.close()


@router.post("/close")
def execute_year_end_close(payload: YearEndCloseRequest, request: Request):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        ensure_audit_storage(conn)
        fiscal_year = payload.fiscal_year

        with conn.cursor() as cur:
            cur.execute(
                "SELECT close_id FROM year_end_closes WHERE fiscal_year = %s",
                (fiscal_year,),
            )
            if cur.fetchone() is not None:
                raise HTTPException(status_code=400, detail="year_already_closed")

        checklist_items = _get_checklist(conn, fiscal_year)
        checklist = _checklist_summary(checklist_items)
        if checklist["total"] > 0 and (not checklist["all_complete"]) and not payload.force:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "checklist_incomplete",
                    "completed": checklist["completed"],
                    "total": checklist["total"],
                },
            )

        summary = _compute_summary(conn, fiscal_year)
        gains = _compute_capital_gains(conn, fiscal_year)
        rollover = _insert_rollover_marker(conn, fiscal_year, summary["net_income"])

        with conn.cursor() as cur:
            summary_json = json.dumps(
                {
                    "summary": {
                        "total_revenue": summary["total_revenue"],
                        "total_expenses": summary["total_expenses"],
                        "net_income": summary["net_income"],
                    },
                    "capital_gains": gains["capital_gains"],
                }
            )
            cur.execute(
                """
                INSERT INTO year_end_closes (
                    fiscal_year, status, total_revenue, total_expenses,
                    net_income, retained_earnings_rollover, capital_gains,
                    notes, executed_by, closed_at, summary_json
                )
                VALUES (%s, 'closed', %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb)
                RETURNING close_id, closed_at
                """,
                (
                    fiscal_year,
                    summary["total_revenue"],
                    summary["total_expenses"],
                    summary["net_income"],
                    rollover["amount"],
                    gains["capital_gains"],
                    payload.notes,
                    "web_app",
                    summary_json,
                ),
            )
            row = cur.fetchone()

        event = AuditEvent(
            module="year_end",
            entity_type="year_end_close",
            entity_id=str(fiscal_year),
            action="year_end_closed",
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before={
                "status": "open",
                "force": payload.force,
            },
            after={
                "status": "closed",
                "summary": {
                    **summary,
                    "capital_gains": gains["capital_gains"],
                    "retained_earnings_rollover": rollover["amount"],
                },
                "notes": payload.notes,
            },
            evidence_links=[
                f"year_end_closes:{fiscal_year}",
                f"year_end_rollovers:{rollover['rollover_id']}",
            ],
            retention_until=datetime(fiscal_year + 6, 12, 31).date(),
            note="Year-end close audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)
        conn.commit()

        return {
            "status": "closed",
            "message": f"Fiscal year {fiscal_year} closed successfully.",
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
                "retained_earnings_rollover": rollover["amount"],
                "rollover_direction": rollover["direction"],
                "closed_at": row[1].isoformat() if hasattr(row[1], "isoformat") else None,
            },
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"year_end_close_failed: {exc}") from exc
    finally:
        conn.close()


@router.get("/report/{fiscal_year}")
def get_year_end_report(fiscal_year: int):
    conn = get_connection()
    try:
        _ensure_tables(conn)
        summary = _compute_summary(conn, fiscal_year)
        gains = _compute_capital_gains(conn, fiscal_year)
        checklist_items = _get_checklist(conn, fiscal_year)
        checklist = _checklist_summary(checklist_items)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT close_id, status, notes, executed_by, closed_at
                FROM year_end_closes
                WHERE fiscal_year = %s
                """,
                (fiscal_year,),
            )
            close_row = cur.fetchone()

            cur.execute(
                """
                SELECT rollover_id, account_code, account_name,
                       amount, direction, created_at, metadata
                FROM year_end_rollovers
                WHERE fiscal_year = %s
                ORDER BY rollover_id
                """,
                (fiscal_year,),
            )
            rollover_rows = cur.fetchall()

        rollovers = [
            {
                "rollover_id": r[0],
                "account_code": r[1],
                "account_name": r[2],
                "amount": float(r[3] or 0.0),
                "direction": r[4],
                "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else None,
                "metadata": r[6],
            }
            for r in rollover_rows
        ]

        return {
            "fiscal_year": fiscal_year,
            "status": close_row[1] if close_row else "open",
            "closed": close_row is not None,
            "notes": close_row[2] if close_row else None,
            "executed_by": close_row[3] if close_row else None,
            "closed_at": close_row[4].isoformat() if close_row and hasattr(close_row[4], "isoformat") else None,
            "summary": {
                **summary,
                "capital_gains": gains["capital_gains"],
            },
            "capital_gains": gains,
            "checklist": {
                "summary": checklist,
                "items": checklist_items,
            },
            "rollovers": rollovers,
        }
    finally:
        conn.close()
