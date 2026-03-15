"""Customers API Router: search/autocomplete for booking form and full customer list"""
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


@router.get("/")
def list_all_customers():
    """List all customers/clients for Customer Management view.
    
    Returns fields:
    - client_id, client_name, client_type, phone, email, company_name
    - is_gst_exempt, last_booking_date
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 
                cl.client_id,
                cl.client_name,
                cl.client_type,
                cl.phone,
                cl.email,
                cl.company_name,
                cl.is_gst_exempt,
                MAX(c.charter_date) as last_booking_date
            FROM clients cl
            LEFT JOIN charters c ON cl.client_id = c.client_id
            GROUP BY cl.client_id, cl.client_name, cl.client_type, cl.phone, 
                     cl.email, cl.company_name, cl.is_gst_exempt
            ORDER BY cl.client_name
            """
        )
        customers = []
        for row in cur.fetchall():
            customers.append(
                {
                    "id": row[0],
                    "client_id": row[0],
                    "client_name": row[1] or "",
                    "client_type": row[2] or "Individual",
                    "phone": row[3] or "",
                    "email": row[4] or "",
                    "company_name": row[5] or "",
                    "is_gst_exempt": row[6] or False,
                    "last_booking_date": str(row[7]) if row[7] else None,
                }
            )
        return customers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list customers: {e}")
    finally:
        cur.close()
        conn.close()
