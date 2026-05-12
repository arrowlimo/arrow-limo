from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/cash-box", tags=["cash-box"])


def _audit_actor(request: Request | None) -> AuditEventActor:
    if request is None:
        return AuditEventActor(actor_type="system", username="system")
    username = request.headers.get("X-User-Name") or request.headers.get(
        "X-User"
    )
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


def _load_cash_box_snapshot(conn, txn_id: int) -> dict | None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, transaction_date, txn_type, transaction_type,
                   description, amount, reference, notes,
                   created_at, updated_at
            FROM cash_box_transactions
            WHERE id = %s
            """,
            (txn_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "transaction_date": row[1].isoformat() if row[1] else None,
            "txn_type": row[2],
            "transaction_type": row[3],
            "description": row[4],
            "amount": float(row[5] or 0),
            "reference": row[6],
            "notes": row[7],
            "created_at": row[8].isoformat() if row[8] else None,
            "updated_at": row[9].isoformat() if row[9] else None,
        }
    finally:
        cur.close()


class CashBoxTxnUpsert(BaseModel):
    date: date
    type: str = Field(pattern="^(cash_in|cash_out)$")
    description: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)


def _ensure_table(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cash_box_transactions (
                id SERIAL PRIMARY KEY,
                transaction_date DATE NOT NULL,
                txn_type TEXT NOT NULL,
                description TEXT NOT NULL,
                amount NUMERIC(12,2) NOT NULL,
                reference TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )

        # Schema drift guard: normalize legacy table variants.
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'cash_box_transactions'
            """
        )
        cols = {r[0] for r in cur.fetchall()}

        if "id" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN id BIGSERIAL")
        if "transaction_date" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN transaction_date DATE")
            if "date" in cols:
                cur.execute(
                    "UPDATE cash_box_transactions SET transaction_date = date WHERE transaction_date IS NULL"
                )
        if "txn_type" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN txn_type TEXT")
            if "type" in cols:
                cur.execute(
                    "UPDATE cash_box_transactions SET txn_type = type WHERE txn_type IS NULL"
                )
            if "transaction_type" in cols:
                cur.execute(
                    "UPDATE cash_box_transactions SET txn_type = transaction_type WHERE txn_type IS NULL"
                )
        if "transaction_type" in cols and "txn_type" in cols:
            cur.execute(
                "UPDATE cash_box_transactions SET transaction_type = COALESCE(transaction_type, txn_type)"
            )
        if "description" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN description TEXT")
        if "amount" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN amount NUMERIC(12,2) DEFAULT 0")
        if "reference" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN reference TEXT")
        if "notes" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN notes TEXT")
        if "updated_at" not in cols:
            cur.execute("ALTER TABLE cash_box_transactions ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW()")

        conn.commit()
    finally:
        cur.close()


def _has_column(conn, table_name: str, column_name: str) -> bool:
    cur = conn.cursor()
    try:
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
    finally:
        cur.close()


def _resolve_legacy_transaction_type(conn, txn_type: str) -> str:
    """Map canonical cash_in/cash_out to legacy transaction_type enums."""
    default_map = {
        "cash_in": "deposit_to_bank",
        "cash_out": "withdrawal_from_bank",
    }
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT transaction_type
            FROM cash_box_transactions
            WHERE transaction_type IS NOT NULL
            """
        )
        values = [str((r[0] or "")).strip() for r in cur.fetchall() if r[0]]
    except Exception:
        values = []
    finally:
        cur.close()

    if not values:
        return default_map.get(txn_type, "adjustment")

    lower_values = [(v, v.lower()) for v in values]
    if txn_type == "cash_in":
        for raw, low in lower_values:
            if any(k in low for k in ["in", "credit", "deposit", "receive"]):
                return raw
    else:
        for raw, low in lower_values:
            if any(k in low for k in ["out", "debit", "expense", "payment"]):
                return raw

    return default_map.get(txn_type, values[0])


@router.get("/transactions")
def list_transactions(
    date: str | None = Query(default=None),
    type: str | None = Query(default=None),
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        sql = """
             SELECT id, transaction_date, txn_type, transaction_type,
                 description, amount, reference, notes
            FROM cash_box_transactions
            WHERE 1=1
        """
        params: list[object] = []
        if date:
            sql += " AND transaction_date = %s"
            params.append(date)
        if type:
            sql += " AND txn_type = %s"
            params.append(type)

        sql += " ORDER BY transaction_date ASC, id ASC"
        cur.execute(sql, params)
        rows = cur.fetchall()

        out = []
        running = 0.0
        for row in rows:
            raw_type = row[2] or row[3] or ""
            norm_type = str(raw_type).lower()
            if norm_type in {"cash_in", "deposit_to_bank", "credit"}:
                ui_type = "cash_in"
            elif norm_type in {"cash_out", "withdrawal_from_bank", "debit"}:
                ui_type = "cash_out"
            else:
                ui_type = "cash_out"

            amount = float(row[5] or 0)
            if ui_type == "cash_in":
                running += amount
            else:
                running -= amount
            out.append(
                {
                    "id": int(row[0]),
                    "date": row[1].isoformat() if row[1] else None,
                    "type": ui_type,
                    "description": row[4] or "",
                    "amount": amount,
                    "reference": row[6] or "",
                    "notes": row[7] or "",
                    "balance": round(running, 2),
                }
            )

        return out
    finally:
        cur.close()


@router.post("/transactions")
def create_transaction(
    payload: CashBoxTxnUpsert,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        use_transaction_type = _has_column(conn, "cash_box_transactions", "transaction_type")
        cols = ["transaction_date", "txn_type", "description", "amount", "reference", "notes"]
        values = [
            payload.date,
            payload.type,
            payload.description.strip(),
            payload.amount,
            payload.reference.strip() if payload.reference else None,
            payload.notes.strip() if payload.notes else None,
        ]
        if use_transaction_type:
            cols.append("transaction_type")
            values.append(_resolve_legacy_transaction_type(conn, payload.type))

        placeholders = ", ".join(["%s"] * len(values))
        cur.execute(
            f"INSERT INTO cash_box_transactions ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
            values,
        )
        row = cur.fetchone()

        ensure_audit_storage(conn)
        after_snapshot = _load_cash_box_snapshot(conn, int(row[0]))
        record_audit_event(
            conn,
            AuditEvent(
                module="cash_box",
                entity_type="cash_box_transaction",
                entity_id=str(row[0]),
                action="create_transaction",
                source="api",
                actor=_audit_actor(request),
                before=None,
                after=after_snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Cash box transaction created",
            ),
            ensure_storage=False,
            commit=False,
        )

        conn.commit()
        return {"status": "created", "id": int(row[0])}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"create_failed: {exc}") from exc
    finally:
        cur.close()


@router.put("/transactions/{txn_id}")
def update_transaction(
    txn_id: int,
    payload: CashBoxTxnUpsert,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        before_snapshot = _load_cash_box_snapshot(conn, txn_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="transaction_not_found")

        use_transaction_type = _has_column(conn, "cash_box_transactions", "transaction_type")
        assignments = [
            "transaction_date = %s",
            "txn_type = %s",
            "description = %s",
            "amount = %s",
            "reference = %s",
            "notes = %s",
            "updated_at = NOW()",
        ]
        values = [
            payload.date,
            payload.type,
            payload.description.strip(),
            payload.amount,
            payload.reference.strip() if payload.reference else None,
            payload.notes.strip() if payload.notes else None,
        ]
        if use_transaction_type:
            assignments.append("transaction_type = %s")
            values.append(_resolve_legacy_transaction_type(conn, payload.type))
        values.append(txn_id)

        cur.execute(
            f"UPDATE cash_box_transactions SET {', '.join(assignments)} WHERE id = %s",
            values,
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="transaction_not_found")

        ensure_audit_storage(conn)
        after_snapshot = _load_cash_box_snapshot(conn, txn_id)
        record_audit_event(
            conn,
            AuditEvent(
                module="cash_box",
                entity_type="cash_box_transaction",
                entity_id=str(txn_id),
                action="update_transaction",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=after_snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Cash box transaction updated",
            ),
            ensure_storage=False,
            commit=False,
        )

        conn.commit()
        return {"status": "updated", "id": txn_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"update_failed: {exc}") from exc
    finally:
        cur.close()


@router.delete("/transactions/{txn_id}")
def delete_transaction(
    txn_id: int,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        before_snapshot = _load_cash_box_snapshot(conn, txn_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="transaction_not_found")

        cur.execute("DELETE FROM cash_box_transactions WHERE id = %s", (txn_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="transaction_not_found")

        ensure_audit_storage(conn)
        record_audit_event(
            conn,
            AuditEvent(
                module="cash_box",
                entity_type="cash_box_transaction",
                entity_id=str(txn_id),
                action="delete_transaction",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=None,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Cash box transaction deleted",
            ),
            ensure_storage=False,
            commit=False,
        )

        conn.commit()
        return {"status": "deleted", "id": txn_id}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
