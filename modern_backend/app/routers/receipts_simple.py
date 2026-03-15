"""Simplified Receipts API Router - matches actual database schema"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..db import get_connection

router = APIRouter(prefix="/api/receipts-simple", tags=["receipts-simple"])

# GL accounts that should NEVER have GST calculated
# Includes: Liability accounts (loans), bank charges, interest, financial services, internal transfers
GST_EXEMPT_GL_CODES = {
    '2795',  # Loans & Leases
    '2800',  # Line of Credit  
    '2802',  # Credit Cards Payable
    '2804',  # Vehicle Loans
    '2806',  # Equipment Loans
    '2807',  # Vehicle Leases
    '2808',  # Equipment Leases
    '2810',  # Shareholder Loan (Paul's advances to company)
    '2910',  # ShareHolder Loan (alternate)
    '6100',  # Bank Charges & Interest
    '6101',  # Interest & Late Charges
    '6280',  # Loan Interest & Finance Charges
    '5450',  # Payment Processing Fees (financial services)
    '1135',  # Prepaid Visa Cards (asset; loads are non-taxable)
    '1099',  # Inter-Account Clearing (internal transfers)
}


def determine_receipt_type(desc: str, trans_type: str) -> tuple[str, str]:
    """Determine receipt_type and notes from banking description and transaction type
    
    Args:
        desc: Banking transaction description
        trans_type: 'DEBIT' or 'CREDIT'
        
    Returns:
        tuple of (receipt_type, notes)
    """
    desc_upper = desc.upper() if desc else ""
    
    if trans_type == 'CREDIT':
        # Money coming IN - categorize reversals/refunds
        if 'NSF RETURN' in desc_upper or 'NSF CHECK' in desc_upper or 'RETURNED ITEM' in desc_upper:
            return ('NSF_REVERSAL', 'NSF reversal - payment bounced and returned')
        elif 'CORRECT' in desc_upper:
            return ('CORRECTION', 'Bank correction - transaction reversed')
        elif any(kw in desc_upper for kw in ['REFUND', 'REVERSAL', 'STOP', 'CANCEL']):
            return ('REFUND', 'Refund or reversal')
        else:
            return ('REFUND', 'Credit transaction - reducing expenses')
    else:
        # Money going OUT - categorize expenses/fees  
        if any(kw in desc_upper for kw in ['NSF CHARGE', 'NSF FEE', 'SERVICE CHARGE', 'MONTHLY FEE']):
            return ('BANK_CHARGE', 'Bank fee or NSF charge')
        else:
            return ('EXPENSE', '')  # Normal expense
    

class SimpleReceiptCreate(BaseModel):
    """Receipt creation matching actual database schema"""

    receipt_date: date
    vendor_name: str
    invoice_number: str | None = None
    gross_amount: Decimal
    gst_amount: Decimal | None = None
    gst_code: str | None = None
    category: str | None = None
    description: str | None = None
    vehicle_id: int | None = None
    charter_id: int | None = None  # Charter linking
    employee_id: int | None = None  # Driver linking (reimbursements)
    reserve_number: str | None = None  # Charter reserve number for lookup
    fuel_amount: Decimal | None = None  # Liters of fuel purchased
    gl_account_code: str | None = None
    is_personal: bool = False
    is_driver_personal: bool = False
    is_paper_verified: bool | None = None  # Track if physical paper receipt exists
    banking_transaction_id: int | None = None  # Link to banking transaction for audit trail


class SimpleReceiptResponse(BaseModel):
    receipt_id: int
    receipt_date: date
    vendor_name: str
    invoice_number: str | None
    canonical_vendor: str | None
    gross_amount: Decimal
    gst_amount: Decimal
    gst_code: str | None
    category: str | None
    description: str | None
    vehicle_id: int | None
    fuel_amount: Decimal | None
    gl_account_code: str | None
    gl_account_name: str | None
    is_personal: bool
    is_driver_personal: bool
    is_paper_verified: bool | None = False
    paper_verification_date: date | None = None
    banking_transaction_id: int | None = None
    receipt_type: str | None = 'EXPENSE'
    banking_transaction_type: str | None = None
    notes: str | None = None


@router.get("/vendors")
def get_vendors():
    """Get distinct list of vendor names for autocomplete with standardization
    
    Cached for 1 hour since vendor list changes infrequently
    """
    conn = get_connection()
    cur = conn.cursor()

    # Use materialized view for better performance
    cur.execute(
        """
        SELECT name, canonical
        FROM mv_vendor_list
        LIMIT 5000
    """
    )

    vendors = []
    for row in cur.fetchall():
        vendors.append({"name": row[0], "canonical": row[1] if row[1] else row[0]})

    cur.close()
    conn.close()

    # Return with cache headers (1 hour cache)
    return JSONResponse(
        content=vendors,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Cache-Info": "Vendor list cached for 1 hour",
        },
    )


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
          AND is_voided IS NOT TRUE
          AND exclude_from_reports IS NOT TRUE
          AND is_split_receipt IS NOT TRUE
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
    vendor: str | None = None,
    days_window: int = 7,
    direction: str = "both",  # Changed default from 'after' to 'both'
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
    """Link a receipt to a banking transaction and populate audit fields"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Get banking transaction details
        cur.execute(
            """
            SELECT debit_amount, credit_amount, description
            FROM banking_transactions
            WHERE transaction_id = %s
            """,
            (transaction_id,)
        )
        bank_row = cur.fetchone()
        if not bank_row:
            raise HTTPException(status_code=404, detail="Banking transaction not found")
        
        debit_amt, credit_amt, description = bank_row
        
        # Determine transaction type
        banking_trans_type = 'DEBIT' if debit_amt and debit_amt > 0 else 'CREDIT'
        
        # Determine receipt_type and notes
        receipt_type, notes = determine_receipt_type(description, banking_trans_type)
        
        # Update receipt with banking link and audit fields
        cur.execute(
            """
            UPDATE receipts
            SET banking_transaction_id = %s,
                banking_transaction_type = %s,
                receipt_type = %s,
                notes = %s,
                modified_at = NOW(),
                modified_by = 'api_link'
            WHERE receipt_id = %s
            """,
            (transaction_id, banking_trans_type, receipt_type, notes, receipt_id)
        )
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        # Also update banking_transactions.receipt_id for reverse lookup
        cur.execute(
            """
            UPDATE banking_transactions
            SET receipt_id = %s
            WHERE transaction_id = %s
        """,
            (receipt_id, transaction_id),
        )

        conn.commit()
        cur.close()
        conn.close()

        return {
            "message": "Receipt linked to banking transaction successfully",
            "receipt_type": receipt_type,
            "banking_transaction_type": banking_trans_type
        }

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to link: {e!s}")


@router.post("/", status_code=201)
def create_receipt(receipt: SimpleReceiptCreate):
    """Create new receipt"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Check GL account FIRST to determine if GST-exempt
        gl_account_code = None
        gl_account_name = None
        is_gst_exempt_account = False
        
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
                # Check if this GL account is GST-exempt (loans, bank charges, etc.)
                is_gst_exempt_account = gl_account_code in GST_EXEMPT_GL_CODES

        # Auto-calculate GST if not provided (5% included in gross)
        # BUT skip GST for exempt accounts (loans, bank charges, financial services)
        gst = receipt.gst_amount
        if gst is None and receipt.gross_amount:
            if is_gst_exempt_account or receipt.is_driver_personal:
                gst = Decimal("0")
            else:
                gst = round(float(receipt.gross_amount) * 0.05 / 1.05, 2)

        canonical_vendor = receipt.vendor_name.strip().upper()
        personal_amount = receipt.gross_amount if receipt.is_personal else Decimal("0")

        # Determine GST code based on conditions
        effective_gst_code = receipt.gst_code
        if receipt.is_driver_personal:
            effective_gst_code = "DRIVER_PERSONAL"
            personal_amount = Decimal("0")  # do not count as owner draw
            gst = Decimal("0")
        elif is_gst_exempt_account:
            effective_gst_code = "GST_EXEMPT"
            gst = Decimal("0")

        # Lookup charter_id from reserve_number if provided
        charter_id = receipt.charter_id
        if receipt.reserve_number and not charter_id:
            cur.execute(
                "SELECT charter_id FROM charters WHERE reserve_number = %s",
                (receipt.reserve_number,)
            )
            charter_row = cur.fetchone()
            if charter_row:
                charter_id = charter_row[0]

        cur.execute(
            """
            INSERT INTO receipts (
                receipt_date, vendor_name, canonical_vendor, invoice_number, gross_amount, gst_amount, gst_code,
                category, description, vehicle_id, charter_id, employee_id, reserve_number,
                fuel_amount, owner_personal_amount, gl_account_code, gl_account_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING receipt_id
        """,
            (
                receipt.receipt_date,
                receipt.vendor_name,
                canonical_vendor,
                receipt.invoice_number,
                receipt.gross_amount,
                gst,
                effective_gst_code,
                receipt.category,
                receipt.description,
                receipt.vehicle_id,
                charter_id,
                receipt.employee_id,
                receipt.reserve_number,
                receipt.fuel_amount,
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
            SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, invoice_number, gross_amount,
                   gst_amount, gst_code, category, description, vehicle_id, charter_id, 
                   employee_id, reserve_number, fuel_amount, owner_personal_amount,
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
            "invoice_number": row[4],
            "gross_amount": float(row[5]) if row[5] else 0,
            "gst_amount": float(row[6]) if row[6] else 0,
            "gst_code": row[7],
            "category": row[8],
            "description": row[9],
            "vehicle_id": row[10],
            "charter_id": row[11],
            "employee_id": row[12],
            "reserve_number": row[13],
            "fuel_amount": float(row[14]) if row[14] else None,
            "is_personal": bool(row[15] and float(row[15]) > 0),
            "is_driver_personal": bool(row[7] == "DRIVER_PERSONAL"),
            "gl_account_code": row[16],
            "gl_account_name": row[17],
        }

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=500, detail=f"Failed to create receipt: {e!s}"
        )


@router.get("/")
def get_receipts(
    start_date: date | None = None,
    end_date: date | None = None,
    vendor: str | None = None,
    limit: int = 100,
):
    """Get recent receipts"""
    conn = get_connection()
    cur = conn.cursor()

    query = """
         SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, invoice_number, gross_amount,
             gst_amount, gst_code, category, description, vehicle_id, fuel_amount,
             owner_personal_amount, gl_account_code, gl_account_name
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
                "invoice_number": row[4],
                "gross_amount": float(row[5]) if row[5] else 0,
                "gst_amount": float(row[6]) if row[6] else 0,
                "gst_code": row[7],
                "category": row[8],
                "description": row[9],
                "vehicle_id": row[10],
                "fuel_amount": float(row[11]) if row[11] else None,
                "is_personal": bool(row[12] and float(row[12]) > 0),
                "is_driver_personal": bool(row[7] == "DRIVER_PERSONAL"),
                "gl_account_code": row[13],
                "gl_account_name": row[14],
            }
        )

    cur.close()
    conn.close()

    return receipts


@router.get("/{receipt_id}")
def get_receipt(receipt_id: int):
    """Get a single receipt by ID"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, invoice_number, gross_amount,
               gst_amount, gst_code, category, description, vehicle_id, charter_id,
               employee_id, reserve_number, fuel_amount, owner_personal_amount,
               gl_account_code, gl_account_name, is_paper_verified, paper_verification_date
        FROM receipts
        WHERE receipt_id = %s
        """,
        (receipt_id,),
    )

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return {
        "receipt_id": row[0],
        "receipt_date": row[1],
        "vendor_name": row[2],
        "canonical_vendor": row[3],
        "invoice_number": row[4],
        "gross_amount": float(row[5]) if row[5] else 0,
        "gst_amount": float(row[6]) if row[6] else 0,
        "gst_code": row[7],
        "category": row[8],
        "description": row[9],
        "vehicle_id": row[10],
        "charter_id": row[11],
        "employee_id": row[12],
        "reserve_number": row[13],
        "fuel_amount": float(row[14]) if row[14] else None,
        "is_personal": bool(row[15] and float(row[15]) > 0),
        "is_driver_personal": bool(row[7] == "DRIVER_PERSONAL"),
        "gl_account_code": row[16],
        "gl_account_name": row[17],
        "is_paper_verified": bool(row[18]) if row[18] is not None else False,
        "paper_verification_date": row[19],
    }


@router.put("/{receipt_id}")
def update_receipt(receipt_id: int, receipt: SimpleReceiptCreate):
    """Update an existing receipt"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Check if receipt exists
        cur.execute("SELECT receipt_id FROM receipts WHERE receipt_id = %s", (receipt_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Receipt not found")

        # Check GL account FIRST to determine if GST-exempt
        gl_account_code = None
        gl_account_name = None
        is_gst_exempt_account = False
        
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
                # Check if this GL account is GST-exempt
                is_gst_exempt_account = gl_account_code in GST_EXEMPT_GL_CODES

        # Auto-calculate GST if not provided
        # BUT skip GST for exempt accounts (loans, bank charges, financial services)
        gst = receipt.gst_amount
        if gst is None and receipt.gross_amount:
            if is_gst_exempt_account or receipt.is_driver_personal:
                gst = Decimal("0")
            else:
                gst = round(float(receipt.gross_amount) * 0.05 / 1.05, 2)

        canonical_vendor = receipt.vendor_name.strip().upper()
        personal_amount = receipt.gross_amount if receipt.is_personal else Decimal("0")

        # Driver personal expenses handling
        effective_gst_code = receipt.gst_code
        if receipt.is_driver_personal:
            effective_gst_code = "DRIVER_PERSONAL"
            personal_amount = Decimal("0")
            gst = Decimal("0")
        elif is_gst_exempt_account:
            effective_gst_code = "GST_EXEMPT"
            gst = Decimal("0")

        # Lookup charter_id from reserve_number if provided
        charter_id = receipt.charter_id
        if receipt.reserve_number and not charter_id:
            cur.execute(
                "SELECT charter_id FROM charters WHERE reserve_number = %s",
                (receipt.reserve_number,)
            )
            charter_row = cur.fetchone()
            if charter_row:
                charter_id = charter_row[0]

        cur.execute(
            """
            UPDATE receipts SET
                receipt_date = %s,
                vendor_name = %s,
                canonical_vendor = %s,
                invoice_number = %s,
                gross_amount = %s,
                gst_amount = %s,
                gst_code = %s,
                category = %s,
                description = %s,
                vehicle_id = %s,
                charter_id = %s,
                employee_id = %s,
                reserve_number = %s,
                fuel_amount = %s,
                owner_personal_amount = %s,
                gl_account_code = %s,
                gl_account_name = %s,
                is_paper_verified = COALESCE(%s, is_paper_verified),
                paper_verification_date = CASE WHEN %s = TRUE THEN NOW() ELSE paper_verification_date END
            WHERE receipt_id = %s
            """,
            (
                receipt.receipt_date,
                receipt.vendor_name,
                canonical_vendor,
                receipt.invoice_number,
                receipt.gross_amount,
                gst,
                effective_gst_code,
                receipt.category,
                receipt.description,
                receipt.vehicle_id,
                charter_id,
                receipt.employee_id,
                receipt.reserve_number,
                receipt.fuel_amount,
                personal_amount,
                gl_account_code,
                gl_account_name,
                receipt.is_paper_verified,
                receipt.is_paper_verified,
                receipt_id,
            ),
        )

        conn.commit()

        # Return the updated receipt
        cur.execute(
            """
            SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, invoice_number, gross_amount,
                   gst_amount, gst_code, category, description, vehicle_id, charter_id,
                   employee_id, reserve_number, fuel_amount, owner_personal_amount,
                   gl_account_code, gl_account_name, is_paper_verified, paper_verification_date
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
            "invoice_number": row[4],
            "gross_amount": float(row[5]) if row[5] else 0,
            "gst_amount": float(row[6]) if row[6] else 0,
            "gst_code": row[7],
            "category": row[8],
            "description": row[9],
            "vehicle_id": row[10],
            "charter_id": row[11],
            "employee_id": row[12],
            "reserve_number": row[13],
            "fuel_amount": float(row[14]) if row[14] else None,
            "is_personal": bool(row[15] and float(row[15]) > 0),
            "is_driver_personal": bool(row[7] == "DRIVER_PERSONAL"),
            "gl_account_code": row[16],
            "gl_account_name": row[17],
            "is_paper_verified": bool(row[18]) if row[18] is not None else False,
            "paper_verification_date": row[19],
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=500, detail=f"Failed to update receipt: {e!s}"
        )
