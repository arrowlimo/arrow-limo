"""Employees API Router: drivers and staff listing"""
import os
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException

from ..db import get_connection

router = APIRouter(prefix="/api/employees", tags=["employees"])

# File storage root
FILE_STORAGE_ROOT = Path(os.environ.get("FILE_STORAGE_ROOT", "Z:/limo_files"))


def create_employee_folder(employee_id: int) -> Path:
    """Create employee folder structure from template when new employee is added."""
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
        cur.execute(
            """
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_category
            FROM employees
            ORDER BY first_name, last_name
            LIMIT 100
            """
        )
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
        raise HTTPException(status_code=500, detail=f"Failed to list employees: {e}")
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
        cur.execute(
            """
            SELECT
                employee_id,
                first_name,
                last_name,
                employee_category
            FROM employees
            WHERE COALESCE(employee_category,'') ILIKE 'driver%' OR is_chauffeur = true
            ORDER BY first_name, last_name
            LIMIT 200
            """
        )
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
        raise HTTPException(status_code=500, detail=f"Failed to list drivers: {e}")
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
        raise HTTPException(status_code=500, detail=f"Failed to get employee: {e}")
    finally:
        cur.close()
        conn.close()


@router.post("/")
def create_employee(employee_data: dict):
    """Create new employee and auto-create file storage folder."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO employees (first_name, last_name, employee_category, hire_date, email, phone)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING employee_id
            """,
            (
                employee_data.get("first_name"),
                employee_data.get("last_name"),
                employee_data.get("employee_category"),
                employee_data.get("hire_date"),
                employee_data.get("email"),
                employee_data.get("phone"),
            ),
        )
        employee_id = cur.fetchone()[0]
        conn.commit()

        # Auto-create employee folder structure
        try:
            folder = create_employee_folder(employee_id)
        except Exception as folder_err:
            # Log error but don't fail the employee creation
            print(f"Warning: Failed to create employee folder: {folder_err}")

        return {"employee_id": employee_id, "status": "created"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create employee: {e}")
    finally:
        cur.close()
        conn.close()
