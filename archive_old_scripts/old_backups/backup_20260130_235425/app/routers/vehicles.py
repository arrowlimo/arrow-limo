"""Vehicles API Router: minimal listing for selection in receipts UI"""
from fastapi import APIRouter, HTTPException

from ..db import get_connection

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


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
