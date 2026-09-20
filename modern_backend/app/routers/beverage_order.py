from contextlib import contextmanager
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db import get_connection, return_connection

router = APIRouter(prefix="/api/beverage_order", tags=["beverage-order"])
_CHARTER_NOT_FOUND = "Charter not found"


class BeverageOrderLine(BaseModel):
    id: int | None = None
    name: str
    qty: float = 0
    price: float = 0
    cost: float | None = None


class BeverageOrderUpsert(BaseModel):
    beverage_orders: list[BeverageOrderLine] = []


class BeverageInvoiceSeparatelyRequest(BaseModel):
    charter_id: int
    invoice_separately: bool = True


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


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def _resolve_reserve_number(cur, charter_id: int) -> str:
    cur.execute(
        "SELECT reserve_number FROM charters WHERE charter_id = %s LIMIT 1",
        (charter_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=_CHARTER_NOT_FOUND)
    return str(row[0])


def _latest_order_for_reserve(cur, reserve_number: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT order_id, subtotal, gst, total, order_date
        FROM beverage_orders
        WHERE reserve_number = %s
        ORDER BY order_date DESC, order_id DESC
        LIMIT 1
        """,
        (reserve_number,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in (cur.description or [])]
    return dict(zip(cols, row, strict=False))


@router.get(
    "/print_data",
    responses={
        400: {"description": "charter_id or run_id is required"},
        404: {"description": _CHARTER_NOT_FOUND},
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
            raise HTTPException(status_code=404, detail=_CHARTER_NOT_FOUND)

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
                charter.get("charter_date").isoformat() if charter.get("charter_date") else ""
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


@router.get("/charters/{charter_id}/orders", responses={404: {"description": _CHARTER_NOT_FOUND}})
def get_charter_beverage_orders(charter_id: int):
    """Return latest beverage order lines for a charter."""
    with _db_cursor() as cur:
        reserve_number = _resolve_reserve_number(cur, charter_id)
        order = _latest_order_for_reserve(cur, reserve_number)
        if not order:
            return {"beverage_orders": []}

        items = _load_order_items(cur, int(order.get("order_id")))
        result = [
            {
                "id": idx + 1,
                "name": line.get("name") or "",
                "qty": _to_float(line.get("qty")),
                "price": _to_float(line.get("price")),
            }
            for idx, line in enumerate(items)
        ]
        return {"beverage_orders": result}


@router.put(
    "/charters/{charter_id}/orders",
    responses={
        404: {"description": _CHARTER_NOT_FOUND},
        500: {"description": "failed_to_create_beverage_order"},
    },
)
def upsert_charter_beverage_orders(charter_id: int, payload: BeverageOrderUpsert):
    """Create a new beverage order snapshot for a charter."""
    with _db_cursor() as cur:
        reserve_number = _resolve_reserve_number(cur, charter_id)

        normalized_lines = [
            line
            for line in payload.beverage_orders
            if (line.qty or 0) > 0 and (line.name or "").strip()
        ]

        subtotal = sum(max(float(line.qty), 0.0) * max(float(line.price), 0.0) for line in normalized_lines)
        gst = round(subtotal * 0.05, 2)
        total = round(subtotal + gst, 2)

        cur.execute(
            """
            INSERT INTO beverage_orders
            (reserve_number, order_date, subtotal, gst, total, status)
            VALUES (%s, NOW(), %s, %s, %s, 'pending')
            RETURNING order_id
            """,
            (reserve_number, subtotal, gst, total),
        )
        order_row = cur.fetchone()
        if not order_row:
            raise HTTPException(status_code=500, detail="failed_to_create_beverage_order")
        order_id = int(order_row[0])

        for line in normalized_lines:
            qty = max(float(line.qty), 0.0)
            price = max(float(line.price), 0.0)
            line_total = round(qty * price, 2)
            cur.execute(
                """
                INSERT INTO beverage_order_items
                (order_id, item_id, item_name, quantity, unit_price, total)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (order_id, line.id, (line.name or "").strip(), qty, price, line_total),
            )

        return {
            "ok": True,
            "order_id": order_id,
            "beverage_orders": [
                {
                    "id": line.id,
                    "name": line.name,
                    "qty": line.qty,
                    "price": line.price,
                }
                for line in normalized_lines
            ],
            "totals": {
                "subtotal": subtotal,
                "gst": gst,
                "total": total,
            },
        }


@router.post("/invoice_separately", responses={404: {"description": _CHARTER_NOT_FOUND}})
def set_invoice_beverages_separately(payload: BeverageInvoiceSeparatelyRequest):
    """Toggle separate customer printout on charter for beverage invoicing workflow."""
    with _db_cursor() as cur:
        if not _column_exists(cur, "charters", "separate_customer_printout"):
            return {
                "ok": True,
                "charter_id": payload.charter_id,
                "invoice_separately": payload.invoice_separately,
                "applied": False,
                "reason": "column_missing",
            }

        cur.execute(
            """
            UPDATE charters
            SET separate_customer_printout = %s
            WHERE charter_id = %s
            """,
            (payload.invoice_separately, payload.charter_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=_CHARTER_NOT_FOUND)

    return {
        "ok": True,
        "charter_id": payload.charter_id,
        "invoice_separately": payload.invoice_separately,
        "applied": True,
    }
