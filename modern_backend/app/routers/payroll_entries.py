from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/payroll", tags=["payroll-entries"])


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


def _load_payroll_entry_snapshot(conn, entry_id: int) -> dict | None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, employee_id, year, pay_period,
                   regular_hours, hourly_rate, ot_hours, ot_rate,
                   base_salary, bonus, gratuity, other_benefits,
                   cpp, ei, income_tax, notes,
                   created_at, updated_at
            FROM payroll_entries
            WHERE id = %s
            """,
            (entry_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "employee_id": int(row[1]),
            "year": int(row[2]),
            "pay_period": row[3],
            "regular_hours": float(row[4] or 0),
            "hourly_rate": float(row[5] or 0),
            "ot_hours": float(row[6] or 0),
            "ot_rate": float(row[7] or 0),
            "base_salary": float(row[8] or 0),
            "bonus": float(row[9] or 0),
            "gratuity": float(row[10] or 0),
            "other_benefits": float(row[11] or 0),
            "cpp": float(row[12] or 0),
            "ei": float(row[13] or 0),
            "income_tax": float(row[14] or 0),
            "notes": row[15],
            "created_at": row[16].isoformat() if row[16] else None,
            "updated_at": row[17].isoformat() if row[17] else None,
        }
    finally:
        cur.close()


class PayrollEntryUpsert(BaseModel):
    employee_id: int
    year: int = Field(ge=2000, le=2100)
    pay_period: str = Field(min_length=1, max_length=50)
    regular_hours: float = 0
    hourly_rate: float = 0
    ot_hours: float = 0
    ot_rate: float = 0
    base_salary: float = 0
    bonus: float = 0
    gratuity: float = 0
    other_benefits: float = 0
    cpp: float = 0
    ei: float = 0
    income_tax: float = 0
    notes: str | None = Field(default=None, max_length=1000)


def _ensure_table(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS payroll_entries (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                pay_period TEXT NOT NULL,
                regular_hours NUMERIC NOT NULL DEFAULT 0,
                hourly_rate NUMERIC NOT NULL DEFAULT 0,
                ot_hours NUMERIC NOT NULL DEFAULT 0,
                ot_rate NUMERIC NOT NULL DEFAULT 0,
                base_salary NUMERIC NOT NULL DEFAULT 0,
                bonus NUMERIC NOT NULL DEFAULT 0,
                gratuity NUMERIC NOT NULL DEFAULT 0,
                other_benefits NUMERIC NOT NULL DEFAULT 0,
                cpp NUMERIC NOT NULL DEFAULT 0,
                ei NUMERIC NOT NULL DEFAULT 0,
                income_tax NUMERIC NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


@router.get("/entries")
def list_entries(year: int | None = Query(default=None), conn=Depends(get_connection)):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        sql = """
            SELECT p.id, p.employee_id, p.year, p.pay_period,
                   p.regular_hours, p.hourly_rate, p.ot_hours, p.ot_rate,
                   p.base_salary, p.bonus, p.gratuity, p.other_benefits,
                   p.cpp, p.ei, p.income_tax, p.notes,
                   COALESCE(e.full_name, e.first_name || ' ' || e.last_name, '') AS employee_name
            FROM payroll_entries p
            LEFT JOIN employees e ON e.employee_id = p.employee_id
            WHERE 1=1
        """
        params: list[object] = []
        if year is not None:
            sql += " AND p.year = %s"
            params.append(year)
        sql += " ORDER BY p.year DESC, p.pay_period DESC, p.id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()

        out = []
        for r in rows:
            out.append(
                {
                    "id": int(r[0]),
                    "employee_id": int(r[1]),
                    "year": int(r[2]),
                    "pay_period": r[3],
                    "regular_hours": float(r[4] or 0),
                    "hourly_rate": float(r[5] or 0),
                    "ot_hours": float(r[6] or 0),
                    "ot_rate": float(r[7] or 0),
                    "base_salary": float(r[8] or 0),
                    "bonus": float(r[9] or 0),
                    "gratuity": float(r[10] or 0),
                    "other_benefits": float(r[11] or 0),
                    "cpp": float(r[12] or 0),
                    "ei": float(r[13] or 0),
                    "tax_withheld": float(r[14] or 0),
                    "income_tax": float(r[14] or 0),
                    "notes": r[15] or "",
                    "employee_name": r[16] or "",
                    "gross_pay": round(
                        (float(r[4] or 0) * float(r[5] or 0))
                        + (float(r[6] or 0) * float(r[7] or 0))
                        + float(r[8] or 0)
                        + float(r[9] or 0)
                        + float(r[10] or 0)
                        + float(r[11] or 0),
                        2,
                    ),
                }
            )
        return out
    finally:
        cur.close()


@router.post("/entries")
def create_entry(
    payload: PayrollEntryUpsert,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO payroll_entries (
                employee_id, year, pay_period, regular_hours, hourly_rate,
                ot_hours, ot_rate, base_salary, bonus, gratuity, other_benefits,
                cpp, ei, income_tax, notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                payload.employee_id,
                payload.year,
                payload.pay_period.strip(),
                payload.regular_hours,
                payload.hourly_rate,
                payload.ot_hours,
                payload.ot_rate,
                payload.base_salary,
                payload.bonus,
                payload.gratuity,
                payload.other_benefits,
                payload.cpp,
                payload.ei,
                payload.income_tax,
                payload.notes.strip() if payload.notes else None,
            ),
        )
        row = cur.fetchone()

        ensure_audit_storage(conn)
        after_snapshot = _load_payroll_entry_snapshot(conn, int(row[0]))
        record_audit_event(
            conn,
            AuditEvent(
                module="payroll_entries",
                entity_type="payroll_entry",
                entity_id=str(row[0]),
                action="create_entry",
                source="api",
                actor=_audit_actor(request),
                before=None,
                after=after_snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Payroll entry created",
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


@router.put("/entries/{entry_id}")
def update_entry(
    entry_id: int,
    payload: PayrollEntryUpsert,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        before_snapshot = _load_payroll_entry_snapshot(conn, entry_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="entry_not_found")

        cur.execute(
            """
            UPDATE payroll_entries
            SET employee_id = %s,
                year = %s,
                pay_period = %s,
                regular_hours = %s,
                hourly_rate = %s,
                ot_hours = %s,
                ot_rate = %s,
                base_salary = %s,
                bonus = %s,
                gratuity = %s,
                other_benefits = %s,
                cpp = %s,
                ei = %s,
                income_tax = %s,
                notes = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                payload.employee_id,
                payload.year,
                payload.pay_period.strip(),
                payload.regular_hours,
                payload.hourly_rate,
                payload.ot_hours,
                payload.ot_rate,
                payload.base_salary,
                payload.bonus,
                payload.gratuity,
                payload.other_benefits,
                payload.cpp,
                payload.ei,
                payload.income_tax,
                payload.notes.strip() if payload.notes else None,
                entry_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="entry_not_found")

        ensure_audit_storage(conn)
        after_snapshot = _load_payroll_entry_snapshot(conn, entry_id)
        record_audit_event(
            conn,
            AuditEvent(
                module="payroll_entries",
                entity_type="payroll_entry",
                entity_id=str(entry_id),
                action="update_entry",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=after_snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Payroll entry updated",
            ),
            ensure_storage=False,
            commit=False,
        )

        conn.commit()
        return {"status": "updated", "id": entry_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"update_failed: {exc}") from exc
    finally:
        cur.close()


@router.delete("/entries/{entry_id}")
def delete_entry(
    entry_id: int,
    request: Request,
    conn=Depends(get_connection),
):
    _ensure_table(conn)
    cur = conn.cursor()
    try:
        before_snapshot = _load_payroll_entry_snapshot(conn, entry_id)
        if not before_snapshot:
            raise HTTPException(status_code=404, detail="entry_not_found")

        cur.execute("DELETE FROM payroll_entries WHERE id = %s", (entry_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="entry_not_found")

        ensure_audit_storage(conn)
        record_audit_event(
            conn,
            AuditEvent(
                module="payroll_entries",
                entity_type="payroll_entry",
                entity_id=str(entry_id),
                action="delete_entry",
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=None,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Payroll entry deleted",
            ),
            ensure_storage=False,
            commit=False,
        )

        conn.commit()
        return {"status": "deleted", "id": entry_id}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
