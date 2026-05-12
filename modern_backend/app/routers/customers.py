"""Customers API Router: search/autocomplete for booking form and full"
"customer list"""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _audit_actor(request: Request) -> AuditEventActor:
    username = request.headers.get("X-User-Name") or request.headers.get(
        "X-User"
    )
    role = request.headers.get("X-User-Role")
    user_id = request.headers.get("X-User-Id")
    return AuditEventActor(
        actor_type="user" if username else "service",
        user_id=user_id,
        username=username,
        role=role,
    )


def _fetch_client_snapshot(cur, client_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT client_id, account_number, client_name, account_type,
               primary_phone, email, company_name, is_gst_exempt
        FROM clients
        WHERE client_id = %s
        """,
        (client_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "client_id": row[0],
        "account_number": row[1],
        "client_name": row[2] or "",
        "client_type": row[3] or "Individual",
        "phone": row[4] or "",
        "email": row[5] or "",
        "company_name": row[6] or "",
        "is_gst_exempt": bool(row[7]),
    }


@router.get("/search")
def search_customers(
    q: str = Query("", description="Search term (name or phone)"),
    limit: int = Query(10, ge=1, le=100),
):
    """Search customers by name or phone for autocomplete.

    Uses the existing `clients` table,
    returning fields needed by the LMS booking form.
    """
    q = (q or "").strip()
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not q:
            return {"results": [], "count": 0}
        like = f"%{q}%"
        cur.execute(
            """
            SELECT client_id, client_name, phone, email
            FROM clients
            WHERE COALESCE(client_name,'') ILIKE %s
               OR COALESCE(phone,'') ILIKE %s
            ORDER BY client_name
            LIMIT %s
            """,
            (like, like, limit),
        )
        rows = cur.fetchall()
        results = [
            {
                "client_id": r[0],
                "client_name": r[1] or "",
                "phone": r[2] or "",
                "email": r[3] or "",
            }
            for r in rows
        ]
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to search customers: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.get("/")
def list_all_customers():
    """List all customers/clients for Customer Management view.

    Returns fields:
    - client_id, client_name, client_type, phone, email, company_name
    - is_gst_exempt, last_booking_date
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                cl.client_id,
                cl.client_name,
                cl.account_type,
                cl.primary_phone,
                cl.email,
                cl.company_name,
                cl.is_gst_exempt,
                MAX(c.charter_date) as last_booking_date
            FROM clients cl
            LEFT JOIN charters c ON cl.client_id = c.client_id
            GROUP BY cl.client_id, cl.client_name, cl.account_type, cl.primary_phone, 
                     cl.email, cl.company_name, cl.is_gst_exempt
            ORDER BY cl.client_name
            """)
        customers = []
        for row in cur.fetchall():
            customers.append(
                {
                    "id": row[0],
                    "client_id": row[0],
                    "client_name": row[1] or "",
                    "client_type": row[2] or "Individual",
                    "phone": row[3] or "",
                    "email": row[4] or "",
                    "company_name": row[5] or "",
                    "is_gst_exempt": row[6] or False,
                    "last_booking_date": str(row[7]) if row[7] else None,
                }
            )
        return customers
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to list customers: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.post("/")
def upsert_customer(payload: dict[str, Any], request: Request):
    """Create a new customer or update an existing one."""
    client_name = (payload.get("client_name") or "").strip()
    if not client_name:
        raise HTTPException(status_code=400, detail="client_name_required")

    client_type = (payload.get("client_type") or "Individual").strip()
    phone = (payload.get("phone") or payload.get("primary_phone") or "").strip()
    email = (payload.get("email") or "").strip()
    company_name = (payload.get("company_name") or "").strip()
    is_gst_exempt = bool(payload.get("is_gst_exempt", False))

    conn = get_connection()
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        requested_id = payload.get("client_id") or payload.get("id")
        existing_id = int(requested_id) if requested_id else None

        if existing_id:
            before_snapshot = _fetch_client_snapshot(cur, existing_id)
            if before_snapshot is None:
                raise HTTPException(status_code=404, detail="customer_not_found")

            cur.execute(
                """
                UPDATE clients
                SET client_name = %s,
                    account_type = %s,
                    primary_phone = %s,
                    email = %s,
                    company_name = %s,
                    is_gst_exempt = %s
                WHERE client_id = %s
                """,
                (
                    client_name,
                    client_type,
                    phone,
                    email,
                    company_name,
                    is_gst_exempt,
                    existing_id,
                ),
            )
            after_snapshot = _fetch_client_snapshot(cur, existing_id)
            action = "customer_updated"
            entity_id = str(existing_id)
        else:
            cur.execute(
                "SELECT MAX(CAST(account_number AS INTEGER)) FROM clients "
                "WHERE account_number ~ '^[0-9]+$'"
            )
            max_account = cur.fetchone()[0] or 7604
            next_account_number = str(int(max_account) + 1)

            cur.execute(
                """
                INSERT INTO clients (
                    account_number,
                    client_name,
                    account_type,
                    primary_phone,
                    email,
                    company_name,
                    is_gst_exempt
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING client_id
                """,
                (
                    next_account_number,
                    client_name,
                    client_type,
                    phone,
                    email,
                    company_name,
                    is_gst_exempt,
                ),
            )
            new_client_id = cur.fetchone()[0]
            after_snapshot = _fetch_client_snapshot(cur, int(new_client_id))
            before_snapshot = None
            action = "customer_created"
            entity_id = str(new_client_id)

        record_audit_event(
            conn,
            AuditEvent(
                module="customers",
                entity_type="customer",
                entity_id=entity_id,
                action=action,
                source="api",
                actor=_audit_actor(request),
                before=before_snapshot,
                after=after_snapshot,
                evidence_links=[],
                retention_until=date.today() + timedelta(days=365 * 7),
                note="Customer upsert via API",
            ),
            ensure_storage=False,
            commit=False,
        )
        conn.commit()

        return after_snapshot
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to save customer: {e}"
        )
    finally:
        cur.close()
        conn.close()
