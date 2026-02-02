"""Customers API Router: search/autocomplete for booking form"""
from fastapi import APIRouter, HTTPException, Query

from ..db import get_connection

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("/search")
def search_customers(
    q: str = Query("", description="Search term (name or phone)"),
    limit: int = Query(10, ge=1, le=100),
):
    """Search customers by name or phone for autocomplete.

    Uses the existing `clients` table, returning fields needed by the LMS booking form.
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
            WHERE COALESCE(client_name,'') ILIKE %s OR COALESCE(phone,'') ILIKE %s
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
        raise HTTPException(status_code=500, detail=f"Failed to search customers: {e}")
    finally:
        cur.close()
        conn.close()
