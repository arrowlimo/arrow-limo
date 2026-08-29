from datetime import datetime

from fastapi import Request

from ...audit.engine import ensure_audit_storage, record_audit_event
from ...audit.schemas import AuditEvent, AuditEventActor
from ...db import get_connection, return_connection


def record_auth_event(
    *,
    action: str,
    username: str | None,
    user_id: int | None,
    role: str | None,
    request: Request | None = None,
    note: str | None = None,
) -> None:
    """Best-effort auth audit event write without blocking login flow."""
    conn = None
    try:
        conn = get_connection()
        ensure_audit_storage(conn)
        actor = AuditEventActor(
            actor_type="user" if username else "service",
            user_id=str(user_id) if user_id is not None else None,
            username=username,
            role=role,
        )
        corr = getattr(request.state, "request_id", None) if request else None
        if not corr and request:
            corr = request.headers.get("X-Request-ID", "")[:128] or None
        elif corr:
            corr = str(corr)[:128]
        record_audit_event(
            conn,
            AuditEvent(
                module="driver_auth",
                entity_type="session",
                entity_id=str(user_id) if user_id is not None else (username or "unknown"),
                action=action,
                source="api",
                correlation_id=corr,
                actor=actor,
                before=None,
                after=None,
                evidence_links=[],
                retention_until=datetime(datetime.now().year + 6, 12, 31).date(),
                note=note,
            ),
            ensure_storage=False,
            commit=True,
        )
    except Exception:
        # Auth should continue even if audit storage is temporarily unavailable.
        pass
    finally:
        if conn is not None:
            return_connection(conn)
