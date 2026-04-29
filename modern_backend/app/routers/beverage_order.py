from contextlib import contextmanager
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/beverage_order", tags=["beverage-order"])


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
        return_connection(conn)


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_order_items(cur, order_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT item_name, quantity, unit_price, total
        FROM beverage_order_items
        WHERE order_id = %s
        ORDER BY item_line_id
        """,
        (order_id,),
    )
    item_columns = [d[0] for d in (cur.description or [])]
    items: list[dict[str, Any]] = []
    for row in cur.fetchall():
        src = dict(zip(item_columns, row, strict=False))
        items.append(
            {
                "name": src.get("item_name") or "",
                "qty": _to_float(src.get("quantity")),
                "price": _to_float(src.get("unit_price")),
                "line_total": _to_float(src.get("total")),
            }
        )
    return items


@router.get(
    "/print_data",
    responses={
        400: {"description": "charter_id or run_id is required"},
        404: {"description": "Charter not found"},
    },
)
def get_beverage_order_print_data(
    charter_id: Annotated[int | None, Query()] = None,
    run_id: Annotated[int | None, Query()] = None,
):
    """Return header/items/totals payload used by BeverageOrderPrint.vue."""
    target_charter_id = charter_id or run_id
    if not target_charter_id:
        raise HTTPException(
            status_code=400,
            detail="Provide charter_id or run_id",
        )

    with _db_cursor() as cur:
        # 1) Resolve charter header fields.
        cur.execute(
            """
            SELECT
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                COALESCE(cl.client_name, '') AS client_name,
                COALESCE(
                    NULLIF(TRIM(COALESCE(c.vehicle, '')), ''),
                    NULLIF(TRIM(COALESCE(v.vehicle_number, '')), ''),
                    NULLIF(TRIM(COALESCE(v.license_plate, '')), ''),
                    ''
                ) AS vehicle
            FROM charters c
            LEFT JOIN clients cl ON cl.client_id = c.client_id
            LEFT JOIN vehicles v ON v.vehicle_id = c.vehicle_id
            WHERE c.charter_id = %s
            LIMIT 1
            """,
            (target_charter_id,),
        )
        charter_row = cur.fetchone()
        if not charter_row:
            raise HTTPException(status_code=404, detail="Charter not found")

        charter_columns = [d[0] for d in (cur.description or [])]
        charter = dict(zip(charter_columns, charter_row, strict=False))

        # 2) Find latest beverage order for the reserve number.
        cur.execute(
            """
            SELECT order_id, subtotal, gst, total, order_date
            FROM beverage_orders
            WHERE reserve_number = %s
            ORDER BY order_date DESC, order_id DESC
            LIMIT 1
            """,
            (charter.get("reserve_number"),),
        )
        order_row = cur.fetchone()

        items: list[dict[str, Any]] = []
        subtotal = 0.0
        grand_total = 0.0

        if order_row:
            order_columns = [d[0] for d in (cur.description or [])]
            order = dict(zip(order_columns, order_row, strict=False))

            items = _load_order_items(cur, int(order.get("order_id")))

            subtotal = _to_float(order.get("subtotal"))
            grand_total = _to_float(order.get("total"))

        if not subtotal and items:
            subtotal = sum(_to_float(i.get("line_total")) for i in items)
        if not grand_total:
            grand_total = subtotal

        header = {
            "charter_id": charter.get("charter_id"),
            "charter_number": charter.get("reserve_number"),
            "client_name": charter.get("client_name") or "",
            "charter_date": (
                charter.get("charter_date").isoformat()
                if charter.get("charter_date")
                else ""
            ),
            "vehicle": charter.get("vehicle") or "",
            "run_id": run_id,
        }

        return {
            "header": header,
            "items": items,
            "totals": {
                "subtotal": subtotal,
                "grand_total": grand_total,
            },
        }
