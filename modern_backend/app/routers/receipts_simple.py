"""Simplified Receipts API Router - matches actual database schema"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/receipts-simple", tags=["receipts-simple"])


class SimpleReceiptCreate(BaseModel):
    """Receipt creation matching actual database schema"""

    receipt_date: date
    vendor_name: str
    gross_amount: Decimal
    gst_amount: Optional[Decimal] = None
    gst_code: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    vehicle_id: Optional[int] = None
    gl_account_code: Optional[str] = None
    is_personal: bool = False
    is_driver_personal: bool = False


class SimpleReceiptResponse(BaseModel):
    receipt_id: int
    receipt_date: date
    vendor_name: str
    canonical_vendor: Optional[str]
    gross_amount: Decimal
    gst_amount: Decimal
    gst_code: Optional[str]
    category: Optional[str]
    description: Optional[str]
    vehicle_id: Optional[int]
    gl_account_code: Optional[str]
    gl_account_name: Optional[str]
    is_personal: bool
    is_driver_personal: bool


@router.get("/vendors")
def get_vendors():
    """Get distinct list of vendor names for autocomplete with standardization"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT vendor_name, canonical_vendor
        FROM receipts
        WHERE vendor_name IS NOT NULL
          AND vendor_name != ''
          AND vendor_name != 'BANKING TRANSACTION'
        ORDER BY vendor_name
        LIMIT 5000
    """
    )

    vendors = []
    for row in cur.fetchall():
        vendors.append({"name": row[0], "canonical": row[1] if row[1] else row[0]})

    cur.close()
    conn.close()

    return vendors


@router.get("/vendor-profile")
def get_vendor_profile(vendor: str):
    """Return canonical vendor, most common category, and gst_code for this vendor."""
    conn = get_connection()
    cur = conn.cursor()

    canonical = None
    # Determine canonical vendor by frequency
    cur.execute(
        """
        SELECT canonical_vendor, COUNT(*)
        FROM receipts
        WHERE vendor_name ILIKE %s OR canonical_vendor ILIKE %s
        GROUP BY canonical_vendor
        ORDER BY COUNT(*) DESC
        LIMIT 1
        """,
        (f"%{vendor}%", f"%{vendor}%"),
    )
    row = cur.fetchone()
    if row and row[0]:
        canonical = row[0]

    # Most common category and gst_code for this vendor
    cur.execute(
        """
        SELECT category, gst_code, COUNT(*)
        FROM receipts
        WHERE vendor_name ILIKE %s OR canonical_vendor ILIKE %s
        GROUP BY category, gst_code
        ORDER BY COUNT(*) DESC
        LIMIT 1
        """,
        (f"%{vendor}%", f"%{vendor}%"),
    )
    top = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "canonical_vendor": canonical or vendor.strip().upper(),
        "suggested_category": top[0] if top and top[0] else None,
        "suggested_gst_code": top[1] if top and top[1] else None,
    }


@router.get("/check-duplicates")
def check_duplicate_receipts(
    vendor: str, amount: float, date: date, days_window: int = 7
):
    """Check for existing receipts matching vendor, amount, and date range"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, gross_amount,
               gst_amount, category, description, banking_transaction_id
        FROM receipts
        WHERE vendor_name ILIKE %s
          AND ABS(gross_amount - %s) < 0.01
          AND receipt_date BETWEEN %s - INTERVAL '%s days' AND %s + INTERVAL '%s days'
        ORDER BY receipt_date DESC
        LIMIT 10
    """,
        (f"%{vendor}%", amount, date, days_window, date, days_window),
    )

    duplicates = []
    for row in cur.fetchall():
        duplicates.append(
            {
                "receipt_id": row[0],
                "receipt_date": row[1],
                "vendor_name": row[2],
                "gross_amount": float(row[3]) if row[3] else 0,
                "gst_amount": float(row[4]) if row[4] else 0,
                "category": row[5],
                "description": row[6],
                "banking_transaction_id": row[7],
                "is_matched": row[7] is not None,
            }
        )

    cur.close()
    conn.close()

    return duplicates


@router.get("/match-banking")
def match_to_banking(
    amount: float,
    date: date,
    vendor: Optional[str] = None,
    days_window: int = 7,
    direction: str = "after",
):
    """Find potential banking transaction matches for a receipt.

    Parameters:
    - amount: receipt gross amount
    - date: purchase date
    - vendor: optional vendor filter (ILIKE)
    - days_window: number of days to search (default 7)
    - direction: 'after' (default), 'both', or 'before' indicating
      whether to search after the purchase date, both sides, or before.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Search banking transactions by amount and date range
    # Build time window based on direction
    direction = (direction or "after").lower()
    if direction not in {"after", "both", "before"}:
        direction = "after"

    if direction == "after":
        query = """
            SELECT bt.transaction_id, bt.transaction_date, bt.description,
                   bt.debit_amount, bt.credit_amount, bt.account_number,
                   bt.receipt_id
            FROM banking_transactions bt
            WHERE (
                ABS(bt.debit_amount - %s) < 0.01
                OR ABS(bt.credit_amount - %s) < 0.01)
            AND bt.transaction_date BETWEEN %s AND %s + INTERVAL '%s days'
        """
        params = [amount, amount, date, date, days_window]
    elif direction == "before":
        query = """
            SELECT bt.transaction_id, bt.transaction_date, bt.description,
                   bt.debit_amount, bt.credit_amount, bt.account_number,
                   bt.receipt_id
            FROM banking_transactions bt
            WHERE (
                ABS(bt.debit_amount - %s) < 0.01
                OR ABS(bt.credit_amount - %s) < 0.01)
            AND bt.transaction_date BETWEEN %s - INTERVAL '%s days' AND %s
        """
        params = [amount, amount, date, days_window, date]
    else:  # both
        query = """
            SELECT bt.transaction_id, bt.transaction_date, bt.description,
                   bt.debit_amount, bt.credit_amount, bt.account_number,
                   bt.receipt_id
            FROM banking_transactions bt
            WHERE (
                ABS(bt.debit_amount - %s) < 0.01
                OR ABS(bt.credit_amount - %s) < 0.01)
            AND bt.transaction_date BETWEEN %s - INTERVAL '%s days' AND %s + INTERVAL '%s days'
        """
        params = [amount, amount, date, days_window, date, days_window]

    if vendor:
        query += " AND bt.description ILIKE %s"
        params.append(f"%{vendor}%")

    query += " ORDER BY bt.transaction_date DESC LIMIT 20"

    cur.execute(query, params)

    matches = []
    for row in cur.fetchall():
        matches.append(
            {
                "transaction_id": row[0],
                "transaction_date": row[1],
                "description": row[2],
                "debit_amount": float(row[3]) if row[3] else 0,
                "credit_amount": float(row[4]) if row[4] else 0,
                "account_number": row[5],
                "already_matched": row[6] is not None,
                "existing_receipt_id": row[6],
            }
        )

    cur.close()
    conn.close()

    return matches


@router.post("/{receipt_id}/link-banking/{transaction_id}")
def link_receipt_to_banking(receipt_id: int, transaction_id: int):
    """Link a receipt to a banking transaction"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Update banking transaction with receipt_id
        cur.execute(
            """
            UPDATE banking_transactions
            SET receipt_id = %s
            WHERE transaction_id = %s
        """,
            (receipt_id, transaction_id),
        )

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Banking transaction not found")

        conn.commit()
        cur.close()
        conn.close()

        return {"message": "Receipt linked to banking transaction successfully"}

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to link: {str(e)}")


@router.post("/", status_code=201)
def create_receipt(receipt: SimpleReceiptCreate):
    """Create new receipt"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Auto-calculate GST if not provided (5% included in gross)
        gst = receipt.gst_amount
        if gst is None and receipt.gross_amount:
            gst = round(float(receipt.gross_amount) * 0.05 / 1.05, 2)

        canonical_vendor = receipt.vendor_name.strip().upper()
        personal_amount = receipt.gross_amount if receipt.is_personal else Decimal("0")

        # Driver personal expenses: tag with special gst_code and do not treat as owner draw
        effective_gst_code = receipt.gst_code
        if receipt.is_driver_personal:
            effective_gst_code = "DRIVER_PERSONAL"
            personal_amount = Decimal("0")  # do not count as owner draw
            gst = Decimal("0")

        gl_account_code = None
        gl_account_name = None
        if receipt.gl_account_code:
            gl_account_code = receipt.gl_account_code.strip()
            if gl_account_code:
                cur.execute(
                    "SELECT account_name FROM chart_of_accounts WHERE account_code = %s",
                    (gl_account_code,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=400, detail="GL account code not found"
                    )
                gl_account_name = row[0]

        cur.execute(
            """
            INSERT INTO receipts (
                receipt_date, vendor_name, canonical_vendor, gross_amount, gst_amount, gst_code,
                category, description, vehicle_id, owner_personal_amount, gl_account_code, gl_account_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING receipt_id
        """,
            (
                receipt.receipt_date,
                receipt.vendor_name,
                canonical_vendor,
                receipt.gross_amount,
                gst,
                effective_gst_code,
                receipt.category,
                receipt.description,
                receipt.vehicle_id,
                personal_amount,
                gl_account_code,
                gl_account_name,
            ),
        )

        receipt_id = cur.fetchone()[0]
        conn.commit()

        # Return the created receipt
        cur.execute(
            """
            SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, gross_amount,
                   gst_amount, gst_code, category, description, vehicle_id, owner_personal_amount,
                   gl_account_code, gl_account_name
            FROM receipts
            WHERE receipt_id = %s
        """,
            (receipt_id,),
        )

        row = cur.fetchone()
        cur.close()
        conn.close()

        return {
            "receipt_id": row[0],
            "receipt_date": row[1],
            "vendor_name": row[2],
            "canonical_vendor": row[3],
            "gross_amount": float(row[4]) if row[4] else 0,
            "gst_amount": float(row[5]) if row[5] else 0,
            "gst_code": row[6],
            "category": row[7],
            "description": row[8],
            "vehicle_id": row[9],
            "is_personal": (row[10] or 0) > 0,
            "is_driver_personal": row[6] == "DRIVER_PERSONAL",
            "gl_account_code": row[11],
            "gl_account_name": row[12],
        }

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=500, detail=f"Failed to create receipt: {str(e)}"
        )


@router.get("/")
def get_receipts(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    vendor: Optional[str] = None,
    limit: int = 100,
):
    """Get recent receipts"""
    conn = get_connection()
    cur = conn.cursor()

    query = """
         SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, gross_amount,
             gst_amount, gst_code, category, description, vehicle_id, owner_personal_amount,
             gl_account_code, gl_account_name
        FROM receipts
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND receipt_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND receipt_date <= %s"
        params.append(end_date)
    if vendor:
        query += " AND vendor_name ILIKE %s"
        params.append(f"%{vendor}%")

    query += " ORDER BY receipt_date DESC, receipt_id DESC LIMIT %s"
    params.append(limit)

    cur.execute(query, params)

    receipts = []
    for row in cur.fetchall():
        receipts.append(
            {
                "receipt_id": row[0],
                "receipt_date": row[1],
                "vendor_name": row[2],
                "canonical_vendor": row[3],
                "gross_amount": float(row[4]) if row[4] else 0,
                "gst_amount": float(row[5]) if row[5] else 0,
                "gst_code": row[6],
                "category": row[7],
                "description": row[8],
                "vehicle_id": row[9],
                "is_personal": (row[10] or 0) > 0,
                "is_driver_personal": row[6] == "DRIVER_PERSONAL",
                "gl_account_code": row[11],
                "gl_account_name": row[12],
            }
        )

    cur.close()
    conn.close()

    return receipts
