"""Vehicles API Router: minimal listing for selection in receipts UI"""
import os
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException

from ..db import get_connection

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])

# File storage root
FILE_STORAGE_ROOT = Path(os.environ.get("FILE_STORAGE_ROOT", "Z:/limo_files"))


def create_vehicle_folder(vehicle_number: str) -> Path:
    """Create vehicle folder structure from template when new vehicle is added."""
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



@router.get("/")
def list_vehicles():
    """Return active vehicles with basic display fields.

    Fields returned:
    - vehicle_id
    - vehicle_number
    - license_plate
    - display (vehicle_number + plate)
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT vehicle_id, vehicle_number, license_plate
            FROM vehicles
            WHERE is_active = true
            ORDER BY vehicle_number
            """
        )
        vehicles = []
        for row in cur.fetchall():
            vehicles.append({
                "vehicle_id": row[0],
                "vehicle_number": row[1],
                "license_plate": row[2],
                "display": f"{row[1]} ({row[2]})" if row[1] and row[2] else (row[1] or row[2] or "Unknown")
            })
        return vehicles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list vehicles: {e}")
    finally:
        cur.close()
        conn.close()


@router.post("/")
def create_vehicle(vehicle_data: dict):
    """Create new vehicle and auto-create file storage folder."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO vehicles (vehicle_number, license_plate, vehicle_type, is_active)
            VALUES (%s, %s, %s, %s)
            RETURNING vehicle_id
            """,
            (
                vehicle_data.get("vehicle_number"),
                vehicle_data.get("license_plate"),
                vehicle_data.get("vehicle_type"),
                vehicle_data.get("is_active", True)
            )
        )
        vehicle_id = cur.fetchone()[0]
        conn.commit()
        
        # Auto-create vehicle folder structure
        vehicle_number = vehicle_data.get("vehicle_number")
        if vehicle_number:
            try:
                folder = create_vehicle_folder(vehicle_number)
            except Exception as folder_err:
                # Log error but don't fail the vehicle creation
                print(f"Warning: Failed to create vehicle folder: {folder_err}")
        
        return {"vehicle_id": vehicle_id, "status": "created"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create vehicle: {e}")
    finally:
        cur.close()
        conn.close()
