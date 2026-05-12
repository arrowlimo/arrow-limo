"""Vehicles API Router: minimal listing for selection in receipts UI"""

import os
import shutil
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])

# File storage root
FILE_STORAGE_ROOT = Path(os.environ.get("FILE_STORAGE_ROOT", "Z:/limo_files"))


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


def _get_table_columns(conn, table_name: str) -> set[str]:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            """,
            (table_name,),
        )
        return {row[0] for row in cur.fetchall()}
    finally:
        cur.close()


def _pick_column_expr(columns: set[str], candidates: list[str], default: str = "NULL") -> str:
    for name in candidates:
        if name in columns:
            return name
    return default


def create_vehicle_folder(vehicle_number: str) -> Path:
    """Create vehicle folder structure from template when new vehicle is"
    "added."""

    vehicle_folder = FILE_STORAGE_ROOT / "vehicles" / vehicle_number
    if vehicle_folder.exists():
        return vehicle_folder

    template = FILE_STORAGE_ROOT / "vehicles" / "_TEMPLATE"
    if template.exists():
        shutil.copytree(template, vehicle_folder)
    else:
        # Create manual structure if template missing
        vehicle_folder.mkdir(parents=True, exist_ok=True)
        (vehicle_folder / "maintenance").mkdir(exist_ok=True)
        (vehicle_folder / "inspections").mkdir(exist_ok=True)
        (vehicle_folder / "registration").mkdir(exist_ok=True)
        (vehicle_folder / "insurance").mkdir(exist_ok=True)

    return vehicle_folder


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "") or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


@router.get("/", responses={500: {"description": "Failed to list vehicles"}})
def list_vehicles():
    """Return active vehicles with all display fields for Vehicle Management
    view.

    Fields returned:
    - vehicle_id, vehicle_number, license_plate, make, model, year, type
    - operational_status, next_service_due, passenger_capacity
    - display (vehicle_number + plate)
    - is_active
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        columns = _get_table_columns(conn, "vehicles")
        vehicle_type_expr = _pick_column_expr(columns, ["type", "vehicle_type"])
        op_status_expr = _pick_column_expr(columns, ["operational_status", "status"])
        next_service_expr = _pick_column_expr(
            columns, ["next_service_due", "next_maintenance_date"]
        )
        passenger_cap_expr = _pick_column_expr(columns, ["passenger_capacity", "capacity"])
        is_active_expr = "is_active" if "is_active" in columns else "TRUE"

        where_clause = ""
        if "is_active" in columns:
            where_clause = "WHERE is_active = true"

        cur.execute(
            f"""
            SELECT
                vehicle_id,
                vehicle_number,
                license_plate,
                make,
                model,
                year,
                {vehicle_type_expr} AS vehicle_type,
                {op_status_expr} AS operational_status,
                {next_service_expr} AS next_service_due,
                {passenger_cap_expr} AS passenger_capacity,
                {is_active_expr} AS is_active
            FROM vehicles
            {where_clause}
            ORDER BY vehicle_number
            """
        )
        vehicles = []
        for row in cur.fetchall():
            vehicles.append(
                {
                    "vehicle_id": row[0],
                    "vehicle_number": row[1],
                    "license_plate": row[2],
                    "make": row[3],
                    "model": row[4],
                    "year": row[5],
                    "type": row[6],
                    "operational_status": row[7],
                    "next_service_due": str(row[8]) if row[8] else None,
                    "passenger_capacity": row[9],
                    "is_active": row[10],
                    "display": (
                        f"{row[1]} ({row[2]})"
                        if row[1] and row[2]
                        else (row[1] or row[2] or "Unknown")
                    ),
                }
            )
        return vehicles
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to list vehicles: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.post("/", responses={500: {"description": "Failed to create vehicle"}})
def create_vehicle(vehicle_data: dict, request: Request):
    """Create new vehicle and auto-create file storage folder."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        vehicle_type = vehicle_data.get("vehicle_type") or vehicle_data.get("type")
        cur.execute(
            """
            INSERT INTO vehicles (vehicle_number, license_plate, vehicle_type,
            is_active)
            VALUES (%s, %s, %s, %s)
            RETURNING vehicle_id
            """,
            (
                vehicle_data.get("vehicle_number"),
                vehicle_data.get("license_plate"),
                vehicle_type,
                vehicle_data.get("is_active", True),
            ),
        )
        vehicle_id = cur.fetchone()[0]

        event = AuditEvent(
            module="vehicles",
            entity_type="vehicle",
            entity_id=str(vehicle_id),
            action="vehicle_created",
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before=None,
            after={
                "vehicle_number": vehicle_data.get("vehicle_number"),
                "license_plate": vehicle_data.get("license_plate"),
                "vehicle_type": vehicle_type,
                "is_active": vehicle_data.get("is_active", True),
            },
            evidence_links=[f"vehicles:{vehicle_id}"],
            retention_until=date(date.today().year + 6, 12, 31),
            note="Vehicle create audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)
        conn.commit()

        # Auto-create vehicle folder structure
        vehicle_number = vehicle_data.get("vehicle_number")
        if vehicle_number:
            try:
                create_vehicle_folder(vehicle_number)
            except Exception as folder_err:
                # Log error but don't fail the vehicle creation
                print(
                    f"Warning: Failed to create vehicle folder: {folder_err}"
                )

        return {"vehicle_id": vehicle_id, "status": "created"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to create vehicle: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.put("/{vehicle_id}", responses={500: {"description": "Failed to update vehicle"}})
def update_vehicle(vehicle_id: int, vehicle_data: dict, request: Request):
    """Update an existing vehicle core fields with audit logging."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        cur.execute(
            """
            SELECT vehicle_number, license_plate, vehicle_type, is_active
            FROM vehicles
            WHERE vehicle_id = %s
            """,
            (vehicle_id,),
        )
        before = cur.fetchone()
        if not before:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        vehicle_type = vehicle_data.get("vehicle_type") or vehicle_data.get("type")
        cur.execute(
            """
            UPDATE vehicles
            SET vehicle_number = COALESCE(%s, vehicle_number),
                license_plate = COALESCE(%s, license_plate),
                vehicle_type = COALESCE(%s, vehicle_type),
                is_active = COALESCE(%s, is_active)
            WHERE vehicle_id = %s
            """,
            (
                vehicle_data.get("vehicle_number"),
                vehicle_data.get("license_plate"),
                vehicle_type,
                vehicle_data.get("is_active"),
                vehicle_id,
            ),
        )

        event = AuditEvent(
            module="vehicles",
            entity_type="vehicle",
            entity_id=str(vehicle_id),
            action="vehicle_updated",
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before={
                "vehicle_number": before[0],
                "license_plate": before[1],
                "vehicle_type": before[2],
                "is_active": bool(before[3]),
            },
            after={
                "vehicle_number": vehicle_data.get("vehicle_number", before[0]),
                "license_plate": vehicle_data.get("license_plate", before[1]),
                "vehicle_type": vehicle_type or before[2],
                "is_active": vehicle_data.get("is_active", bool(before[3])),
            },
            evidence_links=[f"vehicles:{vehicle_id}"],
            retention_until=date(date.today().year + 6, 12, 31),
            note="Vehicle update audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)

        conn.commit()
        return {"status": "updated", "vehicle_id": vehicle_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to update vehicle: {e}"
        )
    finally:
        cur.close()
        conn.close()
