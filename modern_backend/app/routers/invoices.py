"""Invoices API Router"""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

# Constants
ERROR_INVOICE_NOT_FOUND = "Invoice not found"


# Pydantic Models
class InvoiceCreate(BaseModel):
    charter_id: int | None = None
    customer_id: int | None = None
    invoice_number: str
    invoice_date: date
    due_date: date
    amount: Decimal
    gst: Decimal
    description: str | None = None


class InvoiceUpdate(BaseModel):
    invoice_date: date | None = None
    due_date: date | None = None
    amount: Decimal | None = None
    gst: Decimal | None = None
    description: str | None = None
    status: str | None = None


class InvoiceResponse(BaseModel):
    invoice_id: int
    charter_id: int | None
    customer_id: int | None
    customer_name: str | None
    invoice_number: str
    invoice_date: date
    due_date: date
    amount: Decimal
    gst: Decimal
    total: Decimal
    status: str
    paid_date: date | None
    description: str | None
    created_at: datetime | None


@router.get("/")
def get_invoices(
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    customer_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get invoices with optional filters"""
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT
            i.invoice_id,
            c.charter_id,
            c.client_id AS customer_id,
            COALESCE(
                c.client_display_name,
                cl.client_name,
                cl.company_name,
                ''
            ) as customer_name,
            i.invoice_number,
            i.invoice_date,
            i.due_date,
            (COALESCE(i.subtotal_taxable, 0) + COALESCE(i.subtotal_non_taxable, 0)) as amount,
            COALESCE(i.gst_amount, 0) as gst,
            COALESCE(i.invoice_total, 0) as total,
            CASE
                WHEN COALESCE(i.paid, false) = true OR LOWER(COALESCE(i.invoice_status, '')) = 'paid' THEN 'paid'
                WHEN i.due_date < CURRENT_DATE THEN 'overdue'
                ELSE 'unpaid'
            END as status,
            NULL::date as paid_date,
            i.notes as description,
            i.created_at
        FROM invoices i
        LEFT JOIN charters c ON c.reserve_number = i.reserve_number
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE 1=1
    """
    params = []

    if status:
        if status == "paid":
            query += " AND (COALESCE(i.paid, false) = true OR LOWER(COALESCE(i.invoice_status, '')) = 'paid')"
        elif status == "unpaid":
            query += " AND COALESCE(i.paid, false) = false AND i.due_date >= CURRENT_DATE"
        elif status == "overdue":
            query += " AND COALESCE(i.paid, false) = false AND i.due_date < CURRENT_DATE"

    if start_date:
        query += " AND i.invoice_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND i.invoice_date <= %s"
        params.append(end_date)
    if customer_id:
        query += " AND c.client_id = %s"
        params.append(customer_id)

    query += (
        " ORDER BY i.invoice_date DESC, i.invoice_id DESC LIMIT %s OFFSET %s"
    )
    params.extend([limit, offset])

    cur.execute(query, params)

    invoices = []
    for row in cur.fetchall():
        invoices.append(
            {
                "invoice_id": row[0],
                "charter_id": row[1],
                "customer_id": row[2],
                "customer_name": row[3],
                "invoice_number": row[4],
                "invoice_date": row[5],
                "due_date": row[6],
                "amount": float(row[7]) if row[7] else 0,
                "gst": float(row[8]) if row[8] else 0,
                "total": float(row[9]) if row[9] else 0,
                "status": row[10],
                "paid_date": row[11],
                "description": row[12],
                "created_at": row[13],
            }
        )

    cur.close()
    conn.close()

    return invoices


@router.get("/{invoice_id}")
def get_invoice(invoice_id: int):
    """Get single invoice details"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            i.invoice_id,
            c.charter_id,
            c.client_id AS customer_id,
            COALESCE(
                c.client_display_name,
                cl.client_name,
                cl.company_name,
                ''
            ) as customer_name,
            i.invoice_number,
            i.invoice_date,
            i.due_date,
            (COALESCE(i.subtotal_taxable, 0) + COALESCE(i.subtotal_non_taxable, 0)) as amount,
            COALESCE(i.gst_amount, 0) as gst,
            COALESCE(i.invoice_total, 0) as total,
            CASE
                WHEN COALESCE(i.paid, false) = true OR LOWER(COALESCE(i.invoice_status, '')) = 'paid' THEN 'paid'
                WHEN i.due_date < CURRENT_DATE THEN 'overdue'
                ELSE 'unpaid'
            END as status,
            NULL::date as paid_date,
            i.notes as description,
            i.created_at
        FROM invoices i
        LEFT JOIN charters c ON c.reserve_number = i.reserve_number
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE i.invoice_id = %s
    """,
        (invoice_id,),
    )

    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=ERROR_INVOICE_NOT_FOUND)

    invoice = {
        "invoice_id": row[0],
        "charter_id": row[1],
        "customer_id": row[2],
        "customer_name": row[3],
        "invoice_number": row[4],
        "invoice_date": row[5],
        "due_date": row[6],
        "amount": float(row[7]) if row[7] else 0,
        "gst": float(row[8]) if row[8] else 0,
        "total": float(row[9]) if row[9] else 0,
        "status": row[10],
        "paid_date": row[11],
        "description": row[12],
        "created_at": row[13],
    }

    cur.close()
    conn.close()

    return invoice


@router.post("/", status_code=201)
def create_invoice(invoice: InvoiceCreate):
    """Create new invoice"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        reserve_number = None
        if invoice.charter_id is not None:
            cur.execute(
                "SELECT reserve_number FROM charters WHERE charter_id = %s",
                (invoice.charter_id,),
            )
            row = cur.fetchone()
            reserve_number = row[0] if row else None

        cur.execute(
            """
            INSERT INTO invoices (
                reserve_number,
                invoice_number,
                invoice_date,
                due_date,
                subtotal_taxable,
                gst_amount,
                subtotal_non_taxable,
                invoice_total,
                total_payments,
                balance_due,
                paid,
                invoice_status,
                notes,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING invoice_id
        """,
            (
                reserve_number,
                invoice.invoice_number,
                invoice.invoice_date,
                invoice.due_date,
                invoice.amount,
                invoice.gst,
                Decimal("0"),
                invoice.amount + invoice.gst,
                Decimal("0"),
                invoice.amount + invoice.gst,
                False,
                "unpaid",
                invoice.description,
            ),
        )

        invoice_id = cur.fetchone()[0]
        conn.commit()

        cur.close()
        conn.close()

        return {
            "invoice_id": invoice_id,
            "message": "Invoice created successfully",
        }

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to create invoice: {e!s}"
        )


@router.put("/{invoice_id}")
def update_invoice(invoice_id: int, invoice: InvoiceUpdate):
    """Update existing invoice"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        updates = []
        params = []

        if invoice.invoice_date is not None:
            updates.append("invoice_date = %s")
            params.append(invoice.invoice_date)
        if invoice.due_date is not None:
            updates.append("due_date = %s")
            params.append(invoice.due_date)
        if invoice.amount is not None:
            updates.append("subtotal_taxable = %s")
            params.append(invoice.amount)
        if invoice.gst is not None:
            updates.append("gst_amount = %s")
            params.append(invoice.gst)
        if invoice.description is not None:
            updates.append("notes = %s")
            params.append(invoice.description)
        if invoice.status is not None:
            if invoice.status == "paid":
                updates.append("paid = true")
                updates.append("invoice_status = 'paid'")
            elif invoice.status == "unpaid":
                updates.append("paid = false")
                updates.append("invoice_status = 'unpaid'")

        if invoice.amount is not None or invoice.gst is not None:
            updates.append(
                "invoice_total = COALESCE(subtotal_taxable, 0) + "
                "COALESCE(subtotal_non_taxable, 0) + COALESCE(gst_amount, 0)"
            )
            updates.append(
                "balance_due = GREATEST((COALESCE(subtotal_taxable, 0) + COALESCE(subtotal_non_taxable, 0) + COALESCE(gst_amount, 0)) - COALESCE(total_payments, 0), 0)"
            )

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(invoice_id)
        query = f"UPDATE invoices SET {', '.join(updates)} WHERE invoice_id = %s"

        cur.execute(query, params)

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(
                status_code=404, detail=ERROR_INVOICE_NOT_FOUND
            )

        conn.commit()
        cur.close()
        conn.close()

        return {"message": "Invoice updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to update invoice: {e!s}"
        )


@router.put("/{invoice_id}/mark-paid")
def mark_invoice_paid(invoice_id: int, paid_date: date | None = None):
    """Mark invoice as paid"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        if paid_date is None:
            paid_date = date.today()

        cur.execute(
            """
            UPDATE invoices
            SET paid = true,
                invoice_status = 'paid',
                finalized_at = COALESCE(finalized_at, %s)
            WHERE invoice_id = %s
        """,
            (paid_date, invoice_id),
        )

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(
                status_code=404, detail=ERROR_INVOICE_NOT_FOUND
            )

        conn.commit()
        cur.close()
        conn.close()

        return {"message": "Invoice marked as paid"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to mark invoice as paid: {e!s}"
        )


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int):
    """Delete invoice"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            "DELETE FROM invoices WHERE invoice_id = %s", (invoice_id,)
        )

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(
                status_code=404, detail=ERROR_INVOICE_NOT_FOUND
            )

        conn.commit()
        cur.close()
        conn.close()

        return {"message": "Invoice deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(  # noqa: B904
            status_code=500, detail=f"Failed to delete invoice: {e!s}"
        )


@router.get("/stats/summary")
def get_invoice_stats():
    """Get invoice statistics"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE COALESCE(paid, false) = false) as unpaid_count,
            COUNT(*) FILTER (WHERE COALESCE(paid, false) = true) as paid_count,
            COUNT(*) FILTER (WHERE COALESCE(paid, false) = false AND due_date <
            CURRENT_DATE) as overdue_count,
            SUM(COALESCE(balance_due, 0)) FILTER (WHERE COALESCE(paid, false) = false) as
            outstanding_amount,
            SUM(COALESCE(invoice_total, 0)) FILTER (WHERE COALESCE(paid, false) = true) as
            paid_amount
        FROM invoices
    """)

    row = cur.fetchone()

    stats = {
        "unpaid_count": row[0] or 0,
        "paid_count": row[1] or 0,
        "overdue_count": row[2] or 0,
        "outstanding_amount": float(row[3]) if row[3] else 0.0,
        "paid_amount": float(row[4]) if row[4] else 0.0,
    }

    cur.close()
    conn.close()

    return stats
