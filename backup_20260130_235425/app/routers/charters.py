from typing import Any

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Path, Query, Body

from ..db import cursor, get_connection
from ..models.charter_routes import (
    CharterRoute,
    CharterRouteCreate,
    CharterRouteUpdate,
    CharterWithRoutes,
)


router = APIRouter(prefix="/api", tags=["charters"])


@contextmanager
def _db_cursor():
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


@router.get("/charters")
def list_charters(
    q: str | None = Query(default=None, description="Search by charter_id or client name"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    sql = (
        """
        SELECT c.charter_id, c.charter_date, COALESCE(cl.client_name, c.client_id::text) AS client,
               c.vehicle_booked_id, c.driver_name, c.status
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        {where}
        ORDER BY c.charter_date DESC, c.charter_id DESC
        LIMIT %s OFFSET %s
        """
    )
    where = ""
    params: list[Any] = []
    if q:
        where = "WHERE (c.charter_id::text ILIKE %s OR COALESCE(cl.client_name,'') ILIKE %s)"
        like = f"%{q}%"
        params.extend([like, like])
    params.extend([limit, offset])
    with _db_cursor() as cur:
        cur.execute(sql.format(where=where), params)
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
    return [dict(zip(cols, r, strict=False)) for r in rows]


@router.get("/charters/{charter_id}")
def get_charter(
    charter_id: int = Path(..., description="Charter ID"),
):
    with _db_cursor() as cur:
        cur.execute("SELECT * FROM charters WHERE charter_id=%s", (charter_id,))
        row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
    if not row:
        raise HTTPException(status_code=404, detail="charter_not_found")
    return dict(zip(cols, row, strict=False))


@router.patch("/charters/{charter_id}")
def update_charter(
    charter_id: int = Path(...),
    payload: dict[str, Any] | None = None,
):
    # Only allow a safe subset of fields to be updated via this endpoint
    allowed = {
        "status",
        "vehicle_booked_id",
        "driver_name",
        "notes",
        "balance",
        "total_amount_due",
        "charter_date",
        "client_id",
    }
    payload = payload or {}
    updates: dict[str, Any] = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="no_allowed_fields")
    sets = ", ".join([f"{k}=%s" for k in updates])
    params: list[Any] = [*list(updates.values()), charter_id]
    with _db_cursor() as cur:
        cur.execute(f"UPDATE charters SET {sets} WHERE charter_id=%s", params)
        # Return the updated record
        cur.execute("SELECT * FROM charters WHERE charter_id=%s", (charter_id,))
        row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
    if not row:
        raise HTTPException(status_code=404, detail="charter_not_found")
    return dict(zip(cols, row, strict=False))


# ==================== CHARTER ROUTES ENDPOINTS ====================

@router.get("/charters/{charter_id}/routes", response_model=list[CharterRoute])
def get_charter_routes(
    charter_id: int = Path(..., description="Charter ID"),
):
    """Get all routes for a charter, ordered by sequence."""
    with _db_cursor() as cur:
        # Verify charter exists
        cur.execute("SELECT charter_id FROM charters WHERE charter_id = %s", (charter_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="charter_not_found")
        
        cur.execute(
            """
            SELECT * FROM charter_routes 
            WHERE charter_id = %s 
            ORDER BY route_sequence
            """,
            (charter_id,),
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
    return [dict(zip(cols, r, strict=False)) for r in rows]


@router.get("/charters/{charter_id}/with-routes", response_model=CharterWithRoutes)
def get_charter_with_routes(
    charter_id: int = Path(..., description="Charter ID"),
):
    """Get charter with all routes and calculated totals."""
    with _db_cursor() as cur:
        # Get charter with route totals
        cur.execute(
            """
            SELECT 
                c.charter_id, c.reserve_number, c.charter_date, c.client_id, c.status,
                COUNT(r.route_id) as total_routes,
                COALESCE(SUM(r.estimated_duration_minutes), 0) as total_estimated_minutes,
                COALESCE(SUM(r.actual_duration_minutes), 0) as total_actual_minutes,
                COALESCE(SUM(r.estimated_distance_km), 0) as total_estimated_km,
                COALESCE(SUM(r.actual_distance_km), 0) as total_actual_km,
                COALESCE(SUM(r.route_price), 0) as total_route_price
            FROM charters c
            LEFT JOIN charter_routes r ON c.charter_id = r.charter_id
            WHERE c.charter_id = %s
            GROUP BY c.charter_id, c.reserve_number, c.charter_date, c.client_id, c.status
            """,
            (charter_id,),
        )
        charter_row = cur.fetchone()
        if not charter_row:
            raise HTTPException(status_code=404, detail="charter_not_found")
        
        charter_cols = [d[0] for d in (cur.description or [])]
        charter_data = dict(zip(charter_cols, charter_row, strict=False))
        
        # Get all routes
        cur.execute(
            """
            SELECT * FROM charter_routes 
            WHERE charter_id = %s 
            ORDER BY route_sequence
            """,
            (charter_id,),
        )
        route_rows = cur.fetchall()
        route_cols = [d[0] for d in (cur.description or [])]
        routes = [dict(zip(route_cols, r, strict=False)) for r in route_rows]
        
    charter_data["routes"] = routes
    return charter_data


@router.post("/charters/{charter_id}/routes", response_model=CharterRoute, status_code=201)
def create_charter_route(
    charter_id: int = Path(..., description="Charter ID"),
    route: CharterRouteCreate = Body(...),
):
    """Create a new route for a charter."""
    if route.charter_id != charter_id:
        raise HTTPException(status_code=400, detail="charter_id_mismatch")
    
    with _db_cursor() as cur:
        # Verify charter exists
        cur.execute("SELECT charter_id FROM charters WHERE charter_id = %s", (charter_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="charter_not_found")
        
        # Insert route
        cur.execute(
            """
            INSERT INTO charter_routes (
                charter_id, route_sequence, pickup_location, pickup_time,
                dropoff_location, dropoff_time, estimated_duration_minutes,
                actual_duration_minutes, estimated_distance_km, actual_distance_km,
                route_price, route_notes, route_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                route.charter_id,
                route.route_sequence,
                route.pickup_location,
                route.pickup_time,
                route.dropoff_location,
                route.dropoff_time,
                route.estimated_duration_minutes,
                route.actual_duration_minutes,
                route.estimated_distance_km,
                route.actual_distance_km,
                route.route_price,
                route.route_notes,
                route.route_status,
            ),
        )
        new_row = cur.fetchone()
        cols = [d[0] for d in (cur.description or [])]
    
    return dict(zip(cols, new_row, strict=False))


@router.patch("/charters/{charter_id}/routes/{route_id}", response_model=CharterRoute)
def update_charter_route(
    charter_id: int = Path(..., description="Charter ID"),
    route_id: int = Path(..., description="Route ID"),
    route: CharterRouteUpdate = Body(...),
):
    """Update a charter route."""
    route_dict = route.model_dump(exclude_unset=True)
    if not route_dict:
        raise HTTPException(status_code=400, detail="no_fields_to_update")
    
    sets = ", ".join([f"{k} = %s" for k in route_dict.keys()])
    params: list[Any] = [*list(route_dict.values()), route_id, charter_id]
    
    with _db_cursor() as cur:
        cur.execute(
            f"""
            UPDATE charter_routes 
            SET {sets}
            WHERE route_id = %s AND charter_id = %s
            RETURNING *
            """,
            params,
        )
        updated_row = cur.fetchone()
        if not updated_row:
            raise HTTPException(status_code=404, detail="route_not_found")
        cols = [d[0] for d in (cur.description or [])]
    
    return dict(zip(cols, updated_row, strict=False))


@router.delete("/charters/{charter_id}/routes/{route_id}", status_code=204)
def delete_charter_route(
    charter_id: int = Path(..., description="Charter ID"),
    route_id: int = Path(..., description="Route ID"),
):
    """Delete a charter route."""
    with _db_cursor() as cur:
        cur.execute(
            "DELETE FROM charter_routes WHERE route_id = %s AND charter_id = %s",
            (route_id, charter_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="route_not_found")
    return None


@router.post("/charters/{charter_id}/routes/reorder", response_model=list[CharterRoute])
def reorder_charter_routes(
    charter_id: int = Path(..., description="Charter ID"),
    sequence_map: dict[int, int] = Body(..., description="Map of route_id to new sequence number"),
):
    """
    Reorder routes by providing a map of route_id -> new_sequence.
    Automatically handles sequence conflicts by renumbering atomically.
    
    Example: {"123": 1, "124": 2, "125": 3}
    """
    with _db_cursor() as cur:
        # Verify charter exists
        cur.execute("SELECT charter_id FROM charters WHERE charter_id = %s", (charter_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="charter_not_found")
        
        # Verify all route_ids belong to this charter
        route_ids = list(sequence_map.keys())
        cur.execute(
            f"SELECT route_id FROM charter_routes WHERE charter_id = %s AND route_id IN ({','.join(['%s']*len(route_ids))})",
            (charter_id, *route_ids),
        )
        found_ids = {row[0] for row in cur.fetchall()}
        if found_ids != set(route_ids):
            raise HTTPException(status_code=400, detail="invalid_route_ids")
        
        # Temporarily set sequences to high values to avoid conflicts
        # Using route_id + 100000 ensures no overlap with valid sequences
        for route_id in route_ids:
            cur.execute(
                "UPDATE charter_routes SET route_sequence = %s WHERE route_id = %s",
                (route_id + 100000, route_id),
            )
        
        # Now apply the new sequences
        for route_id, new_seq in sequence_map.items():
            cur.execute(
                "UPDATE charter_routes SET route_sequence = %s WHERE route_id = %s",
                (new_seq, route_id),
            )
        
        # Return updated routes in order
        cur.execute(
            "SELECT * FROM charter_routes WHERE charter_id = %s ORDER BY route_sequence",
            (charter_id,),
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
    
    return [dict(zip(cols, r, strict=False)) for r in rows]

