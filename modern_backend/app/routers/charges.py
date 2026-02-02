from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import cursor, get_connection

router = APIRouter(prefix="/api", tags=["charges"])


class ChargeCreate(BaseModel):
    charge_type: str = Field(default="extra")
    amount: float
    description: str | None = None


class ChargeUpdate(BaseModel):
    charge_type: str | None = None
    amount: float | None = None
    description: str | None = None


@router.get("/charters/{charter_id}/charges")
def list_charges(charter_id: int) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            SELECT charge_id, charter_id, charge_type, amount, description, created_at
            FROM charter_charges
            WHERE charter_id = %s
            ORDER BY created_at ASC, charge_id ASC
            """,
            (charter_id,),
        )
        rows = cur.fetchall()
        cols = [d[0] for d in (cur.description or [])]
        items = [dict(zip(cols, r, strict=False)) for r in rows]
    return {"charges": items}


@router.post("/charters/{charter_id}/charges", status_code=201)
def create_charge(charter_id: int, body: ChargeCreate) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO charter_charges (charter_id, charge_type, amount, description)
            VALUES (%s, %s, %s, %s)
            RETURNING charge_id, charter_id, charge_type, amount, description, created_at
            """,
            (charter_id, body.charge_type, body.amount, body.description),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="insert_failed")
        cols = [d[0] for d in (cur.description or [])]
        item = dict(zip(cols, row, strict=False))
    return {"charge": item}


@router.patch("/charges/{charge_id}")
def update_charge(charge_id: int, body: ChargeUpdate) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="no_fields")
    sets = ", ".join([f"{k} = %s" for k in updates])
    values = [*list(updates.values()), charge_id]
    with cursor() as cur:
        cur.execute(
            f"UPDATE charter_charges SET {sets} WHERE charge_id = %s RETURNING charge_id, charter_id, charge_type, amount, description, created_at",
            values,
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="not_found")
        cols = [d[0] for d in (cur.description or [])]
        item = dict(zip(cols, row, strict=False))
    return {"charge": item}


@router.delete("/charges/{charge_id}")
def delete_charge(charge_id: int) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute("DELETE FROM charter_charges WHERE charge_id = %s", (charge_id,))
        deleted = cur.rowcount
        if not deleted:
            raise HTTPException(status_code=404, detail="not_found")
    return {"deleted": True}


# ===== NEW CATALOG & RESERVE-NUMBER ENDPOINTS =====


@router.get("/charges/catalog")
def get_charge_catalog(
    active_only: bool = Query(True, description="Filter to active charges only"),
    charge_type: Optional[str] = Query(
        None,
        description="Filter by type: base_rate, airport_fee, additional, gst",
    ),
):
    """Get catalog of available charge line items for selection in booking form."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        where_clauses = []
        params = []

        if active_only:
            where_clauses.append("is_active = true")

        if charge_type:
            where_clauses.append("charge_type = %s")
            params.append(charge_type)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        cur.execute(
            f"""
            SELECT
                catalog_id, charge_code, charge_name, charge_type,
                default_amount, is_taxable, display_order
            FROM charge_catalog
            WHERE {where_sql}
            ORDER BY display_order, charge_name
            """,
            params,
        )
        rows = cur.fetchall()

        results = [
            {
                "catalog_id": r[0],
                "charge_code": r[1],
                "charge_name": r[2],
                "charge_type": r[3],
                "default_amount": str(r[4]) if r[4] else "0.00",
                "is_taxable": r[5],
                "display_order": r[6],
            }
            for r in rows
        ]

        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load charge catalog: {e}"
        )
    finally:
        cur.close()
        conn.close()


@router.get("/charges/by-reserve/{reserve_number}")
def get_charges_by_reserve(reserve_number: str):
    """Get all charge line items for a booking by reserve_number (business key)."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT charge_id, reserve_number, charge_type, amount, description, created_at
            FROM charges
            WHERE reserve_number = %s
            ORDER BY
                CASE charge_type
                    WHEN 'base_rate' THEN 1
                    WHEN 'airport_fee' THEN 2
                    WHEN 'additional' THEN 3
                    WHEN 'gst' THEN 4
                    ELSE 5
                END,
                charge_id
            """,
            (reserve_number,),
        )
        rows = cur.fetchall()

        results = [
            {
                "charge_id": r[0],
                "reserve_number": r[1],
                "charge_type": r[2],
                "amount": str(r[3]) if r[3] else "0.00",
                "description": r[4],
                "created_at": r[5].isoformat() if r[5] else None,
            }
            for r in rows
        ]

        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load charges: {e}")
    finally:
        cur.close()
        conn.close()
