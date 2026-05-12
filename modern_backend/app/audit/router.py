"""API router for audit checks and year-end package generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..db import get_connection
from .catalog import AUDIT_EVENT_CATALOG, AUDIT_EVENT_SCHEMA, get_system_inventory
from .engine import (
    generate_audit_check_report,
    get_audit_package,
    list_audit_events,
    list_audit_packages,
)
from .packager import generate_notes_to_auditor, generate_year_end_package
from .schemas import AuditCheckRequest

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/inventory")
def audit_inventory():
    return {
        "system_inventory": get_system_inventory(),
        "audit_event_schema": AUDIT_EVENT_SCHEMA,
        "audit_event_catalog": AUDIT_EVENT_CATALOG,
    }


@router.post("/checks")
def audit_checks(payload: AuditCheckRequest, conn=Depends(get_connection)):
    return generate_audit_check_report(conn, payload).model_dump(mode="json")


@router.get("/events")
def audit_events(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    module: str | None = Query(default=None),
    username: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    conn=Depends(get_connection),
):
    return list_audit_events(
        conn,
        date_from=date_from,
        date_to=date_to,
        module=module,
        username=username,
        entity_type=entity_type,
        action=action,
        limit=limit,
        offset=offset,
    )


@router.get("/packages")
def audit_packages(
    fiscal_year: int | None = Query(default=None, ge=2000, le=2100),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn=Depends(get_connection),
):
    return list_audit_packages(
        conn,
        fiscal_year=fiscal_year,
        limit=limit,
        offset=offset,
    )


@router.post("/package/year-end")
def audit_year_end_package(
    payload: AuditCheckRequest, conn=Depends(get_connection)
):
    manifest = generate_year_end_package(conn, payload)
    return manifest.model_dump(mode="json")


@router.get("/package/{package_id}/download")
def audit_download_package(package_id: str, conn=Depends(get_connection)):
    package = get_audit_package(conn, package_id)
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    zip_path = Path(package["zip_path"])
    if not zip_path.exists() or not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Package ZIP not found")

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=zip_path.name,
    )


@router.post("/notes")
def audit_notes(payload: AuditCheckRequest, conn=Depends(get_connection)):
    report = generate_audit_check_report(conn, payload)
    notes = generate_notes_to_auditor(conn, payload, report)
    return {"fiscal_year": payload.fiscal_year, "notes": notes}
