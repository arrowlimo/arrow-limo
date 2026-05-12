"""Employees API Router: drivers and staff listing"""

import os
import shutil
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/employees", tags=["employees"])

# File storage root
FILE_STORAGE_ROOT = Path(os.environ.get("FILE_STORAGE_ROOT", "Z:/limo_files"))


def create_employee_folder(employee_id: int) -> Path:
    """Create employee folder structure from template when new employee is"
    "added."""

    emp_folder = FILE_STORAGE_ROOT / "employees" / str(employee_id)
    if emp_folder.exists():
        return emp_folder

    template = FILE_STORAGE_ROOT / "employees" / "_TEMPLATE"
    if template.exists():
        shutil.copytree(template, emp_folder)
    else:
        # Create manual structure if template missing
        emp_folder.mkdir(parents=True, exist_ok=True)
        (emp_folder / "qualifications").mkdir(exist_ok=True)
        (emp_folder / "permits").mkdir(exist_ok=True)
        (emp_folder / "licenses").mkdir(exist_ok=True)
        (emp_folder / "documents").mkdir(exist_ok=True)

    return emp_folder


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "") or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


@router.get("/")
def list_employees():
    """Return active employees (drivers and staff) with basic info.

    Fields returned:
    - employee_id
    - first_name
    - last_name
    - display (first + last name)
    - employee_type (driver, staff, etc)
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_category
            FROM employees
            ORDER BY first_name, last_name
            LIMIT 100
            """)
        employees = []
        for row in cur.fetchall():
            first_name = row[1] or ""
            last_name = row[2] or ""
            display_name = f"{first_name} {last_name}".strip() or "Unknown"

            employees.append(
                {
                    "employee_id": row[0],
                    "first_name": first_name,
                    "last_name": last_name,
                    "display": display_name,
                    "employee_type": row[3] or "unknown",
                }
            )
        return employees
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to list employees: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.get("/drivers")
def list_drivers():
    """Return active drivers only for assignment dropdown.

    Filters employees where employee_type indicates driver.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_category
            FROM employees
                WHERE COALESCE(employee_category,'') ILIKE 'driver%'
                    OR is_chauffeur = true
            ORDER BY first_name, last_name
            LIMIT 200
            """)
        drivers = []
        for row in cur.fetchall():
            first_name = row[1] or ""
            last_name = row[2] or ""
            display_name = f"{first_name} {last_name}".strip() or "Unknown"
            drivers.append(
                {
                    "employee_id": row[0],
                    "first_name": first_name,
                    "last_name": last_name,
                    "display": display_name,
                }
            )
        return drivers
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to list drivers: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.get("/{employee_id}")
def get_employee(employee_id: int):
    """Get specific employee details"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_category,
                hire_date,
                email,
                phone
            FROM employees
            WHERE employee_id = %s
            """,
            (employee_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404, detail=f"Employee {employee_id} not found"
            )

        return {
            "employee_id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "employee_type": row[3],
            "hire_date": row[4].isoformat() if row[4] else None,
            "email": row[5],
            "phone": row[6],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to get employee: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.post("/")
def create_employee(employee_data: dict, request: Request):
    """Create or update employee and auto-create file storage folder."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        ensure_audit_storage(conn)
        first_name = employee_data.get("first_name")
        last_name = employee_data.get("last_name")
        employee_category = employee_data.get("employee_category")
        hire_date = employee_data.get("hire_date")
        email = employee_data.get("email")
        phone = employee_data.get("phone")

        existing_id = None

        if email:
            cur.execute(
                """
                SELECT employee_id
                FROM employees
                WHERE email IS NOT NULL
                  AND LOWER(TRIM(email)) = LOWER(TRIM(%s))
                ORDER BY employee_id
                LIMIT 1
                """,
                (email,),
            )
            row = cur.fetchone()
            if row:
                existing_id = row[0]

        if existing_id is None:
            cur.execute(
                """
                SELECT employee_id
                FROM employees
                    WHERE LOWER(TRIM(COALESCE(first_name, ''))) =
                        LOWER(TRIM(COALESCE(%s, '')))
                                    AND LOWER(TRIM(COALESCE(last_name, ''))) =
                                            LOWER(TRIM(COALESCE(%s, '')))
                ORDER BY employee_id
                LIMIT 1
                """,
                (first_name, last_name),
            )
            row = cur.fetchone()
            if row:
                existing_id = row[0]

        if existing_id is not None:
            cur.execute(
                """
                SELECT first_name, last_name, employee_category, hire_date, email, phone
                FROM employees
                WHERE employee_id = %s
                """,
                (existing_id,),
            )
            existing_before = cur.fetchone()
            cur.execute(
                """
                UPDATE employees
                SET first_name = COALESCE(%s, first_name),
                    last_name = COALESCE(%s, last_name),
                    employee_category = COALESCE(%s, employee_category),
                    hire_date = COALESCE(%s, hire_date),
                    email = COALESCE(%s, email),
                    phone = COALESCE(%s, phone)
                WHERE employee_id = %s
                """,
                (
                    first_name,
                    last_name,
                    employee_category,
                    hire_date,
                    email,
                    phone,
                    existing_id,
                ),
            )
            employee_id = existing_id
            status = "updated_existing"
            action = "employee_updated"
        else:
            cur.execute(
                """
                INSERT INTO employees (first_name, last_name,
                employee_category, hire_date, email, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING employee_id
                """,
                (
                    first_name,
                    last_name,
                    employee_category,
                    hire_date,
                    email,
                    phone,
                ),
            )
            employee_id = cur.fetchone()[0]
            status = "created"
            action = "employee_created"
            existing_before = None

        event = AuditEvent(
            module="employees",
            entity_type="employee",
            entity_id=str(employee_id),
            action=action,
            source="api",
            correlation_id=request.headers.get("X-Request-ID"),
            actor=_audit_actor(request),
            before=(
                {
                    "first_name": existing_before[0],
                    "last_name": existing_before[1],
                    "employee_category": existing_before[2],
                    "hire_date": str(existing_before[3]) if existing_before[3] else None,
                    "email": existing_before[4],
                    "phone": existing_before[5],
                }
                if existing_before
                else None
            ),
            after={
                "first_name": first_name,
                "last_name": last_name,
                "employee_category": employee_category,
                "hire_date": str(hire_date) if hire_date else None,
                "email": email,
                "phone": phone,
            },
            evidence_links=[f"employees:{employee_id}"],
            retention_until=date(date.today().year + 6, 12, 31),
            note="Employee create/update audit record",
        )
        record_audit_event(conn, event, ensure_storage=False, commit=False)

        conn.commit()

        # Auto-create employee folder structure
        try:
            create_employee_folder(employee_id)
        except Exception as folder_err:
            # Log error but don't fail the employee creation
            print(f"Warning: Failed to create employee folder: {folder_err}")

        return {"employee_id": employee_id, "status": status}
    except Exception as e:
        conn.rollback()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to create employee: {e}"
        )
    finally:
        cur.close()
        conn.close()
