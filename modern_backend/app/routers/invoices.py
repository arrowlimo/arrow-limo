"""Invoices API Router"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


# Pydantic Models
class InvoiceCreate(BaseModel):
    charter_id: Optional[int] = None
    customer_id: Optional[int] = None
    invoice_number: str
    invoice_date: date
    due_date: date
    amount: Decimal
    gst: Decimal
    description: Optional[str] = None


class InvoiceUpdate(BaseModel):
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: Optional[Decimal] = None
    gst: Optional[Decimal] = None
    description: Optional[str] = None
    status: Optional[str] = None


class InvoiceResponse(BaseModel):
    invoice_id: int
    charter_id: Optional[int]
    customer_id: Optional[int]
    customer_name: Optional[str]
    invoice_number: str
    invoice_date: date
    due_date: date
    amount: Decimal
    gst: Decimal
    total: Decimal
    status: str
    paid_date: Optional[date]
    description: Optional[str]
    created_at: Optional[datetime]


@router.get("/")
def get_invoices(
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    customer_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get invoices with optional filters"""
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT
            i.invoice_id,
            i.charter_id,
            i.customer_id,
            COALESCE(c.customer_name, cust.company_name, cust.first_name || ' ' || cust.last_name) as customer_name,
            i.invoice_number,
            i.invoice_date,
            i.due_date,
            i.amount,
            i.gst,
            (i.amount + i.gst) as total,
            CASE
                WHEN i.paid_date IS NOT NULL THEN 'paid'
                WHEN i.due_date < CURRENT_DATE THEN 'overdue'
                ELSE 'unpaid'
            END as status,
            i.paid_date,
            i.description,
            i.created_at
        FROM invoices i
        LEFT JOIN charters c ON i.charter_id = c.charter_id
        LEFT JOIN customers cust ON i.customer_id = cust.customer_id
        WHERE 1=1
    """
    params = []

    if status:
        if status == "paid":
            query += " AND i.paid_date IS NOT NULL"
        elif status == "unpaid":
            query += " AND i.paid_date IS NULL AND i.due_date >= CURRENT_DATE"
        elif status == "overdue":
            query += " AND i.paid_date IS NULL AND i.due_date < CURRENT_DATE"

    if start_date:
        query += " AND i.invoice_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND i.invoice_date <= %s"
        params.append(end_date)
    if customer_id:
        query += " AND i.customer_id = %s"
        params.append(customer_id)

    query += " ORDER BY i.invoice_date DESC, i.invoice_id DESC LIMIT %s OFFSET %s"
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
            i.charter_id,
            i.customer_id,
            COALESCE(c.customer_name, cust.company_name, cust.first_name || ' ' || cust.last_name) as customer_name,
            i.invoice_number,
            i.invoice_date,
            i.due_date,
            i.amount,
            i.gst,
            (i.amount + i.gst) as total,
            CASE
                WHEN i.paid_date IS NOT NULL THEN 'paid'
                WHEN i.due_date < CURRENT_DATE THEN 'overdue'
                ELSE 'unpaid'
            END as status,
            i.paid_date,
            i.description,
            i.created_at
        FROM invoices i
        LEFT JOIN charters c ON i.charter_id = c.charter_id
        LEFT JOIN customers cust ON i.customer_id = cust.customer_id
        WHERE i.invoice_id = %s
    """,
        (invoice_id,),
    )

    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Invoice not found")

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
        cur.execute(
            """
            INSERT INTO invoices (
                charter_id, customer_id, invoice_number, invoice_date,
                due_date, amount, gst, description, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING invoice_id
        """,
            (
                invoice.charter_id,
                invoice.customer_id,
                invoice.invoice_number,
                invoice.invoice_date,
                invoice.due_date,
                invoice.amount,
                invoice.gst,
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
        raise HTTPException(
            status_code=500, detail=f"Failed to create invoice: {str(e)}"
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
            updates.append("amount = %s")
            params.append(invoice.amount)
        if invoice.gst is not None:
            updates.append("gst = %s")
            params.append(invoice.gst)
        if invoice.description is not None:
            updates.append("description = %s")
            params.append(invoice.description)
        if invoice.status is not None:
            if invoice.status == "paid":
                updates.append("paid_date = CURRENT_DATE")
            elif invoice.status == "unpaid":
                updates.append("paid_date = NULL")

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(invoice_id)
        query = f"UPDATE invoices SET {', '.join(updates)} WHERE invoice_id = %s"

        cur.execute(query, params)

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Invoice not found")

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
        raise HTTPException(
            status_code=500, detail=f"Failed to update invoice: {str(e)}"
        )


@router.put("/{invoice_id}/mark-paid")
def mark_invoice_paid(invoice_id: int, paid_date: Optional[date] = None):
    """Mark invoice as paid"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        if paid_date is None:
            paid_date = date.today()

        cur.execute(
            """
            UPDATE invoices
            SET paid_date = %s
            WHERE invoice_id = %s
        """,
            (paid_date, invoice_id),
        )

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Invoice not found")

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
        raise HTTPException(
            status_code=500, detail=f"Failed to mark invoice as paid: {str(e)}"
        )


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int):
    """Delete invoice"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("DELETE FROM invoices WHERE invoice_id = %s", (invoice_id,))

        if cur.rowcount == 0:
            conn.rollback()
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Invoice not found")

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
        raise HTTPException(
            status_code=500, detail=f"Failed to delete invoice: {str(e)}"
        )


@router.get("/stats/summary")
def get_invoice_stats():
    """Get invoice statistics"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE paid_date IS NULL) as unpaid_count,
            COUNT(*) FILTER (WHERE paid_date IS NOT NULL) as paid_count,
            COUNT(*) FILTER (WHERE paid_date IS NULL AND due_date < CURRENT_DATE) as overdue_count,
            SUM(amount + gst) FILTER (WHERE paid_date IS NULL) as outstanding_amount,
            SUM(amount + gst) FILTER (WHERE paid_date IS NOT NULL) as paid_amount
        FROM invoices
    """
    )

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
