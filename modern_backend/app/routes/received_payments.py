"""
Received Payments API
Record customer payments received (cheques, cash, e-transfers, etc.)
Links to charters/invoices or records as unallocated revenue
"""

from datetime import date, datetime

import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_connection

router = APIRouter(prefix="/api/received-payments", tags=["Received Payments"])


def _extract_note_field(notes: str | None, prefixes: tuple[str, ...]) -> str | None:
    """Extract first matching note field value by prefix."""
    if not notes:
        return None
    for raw_line in notes.splitlines():
        line = raw_line.strip()
        lower_line = line.lower()
        for prefix in prefixes:
            lower_prefix = prefix.lower()
            if lower_line.startswith(lower_prefix):
                value = line[len(prefix) :].strip()
                return value or None
    return None


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class ReceivedPaymentCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Payment amount")
    payment_date: date = Field(..., description="Date payment received")
    payment_method: str = Field(..., description="cheque, cash, e-transfer, credit_card, debit")
    payer_name: str = Field(..., description="Who paid (customer/company name)")

    # Cheque-specific fields
    cheque_number: str | None = Field(None, description="Cheque number if payment_method=cheque")
    bank_name: str | None = Field(None, description="Bank name on cheque")

    # Optional allocation
    charter_id: int | None = Field(None, description="Link to specific charter/booking")
    reserve_number: str | None = Field(None, description="Reserve number if linking to charter")

    # Additional details
    notes: str | None = Field(None, description="Additional notes")
    deposit_type: str | None = Field("payment", description="payment, deposit, partial_payment")


class ReceivedPaymentUpdate(BaseModel):
    amount: float | None = None
    payment_date: date | None = None
    payment_method: str | None = None
    payer_name: str | None = None
    cheque_number: str | None = None
    bank_name: str | None = None
    charter_id: int | None = None
    reserve_number: str | None = None
    notes: str | None = None


class ReceivedPaymentResponse(BaseModel):
    payment_id: int
    amount: float
    payment_date: date
    payment_method: str
    payer_name: str
    cheque_number: str | None
    bank_name: str | None
    charter_id: int | None
    reserve_number: str | None
    notes: str | None
    deposit_type: str
    created_at: datetime

    # Related charter info (if linked)
    customer_name: str | None = None
    charter_date: date | None = None
    charter_amount: float | None = None


class PaymentSearchRequest(BaseModel):
    payer_name: str | None = None
    cheque_number: str | None = None
    amount_min: float | None = None
    amount_max: float | None = None
    date_from: date | None = None
    date_to: date | None = None
    payment_method: str | None = None
    unallocated_only: bool = False


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post("/", response_model=dict, status_code=201)
async def record_received_payment(payment: ReceivedPaymentCreate):
    """Record a payment received from customer (cheque, cash, e-transfer,"
    "etc.)"""

    conn = get_connection()
    cur = conn.cursor()

    try:
        resolved_charter_id, resolved_reserve = _resolve_charter_reference(
            cur,
            payment.charter_id,
            payment.reserve_number,
        )

        # Insert payment
        cur.execute(
            """
            INSERT INTO payments (
                charter_id,
                reserve_number,
                amount,
                payment_date,
                payment_method,
                payment_key,
                notes,
                last_updated
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            RETURNING payment_id, created_at
        """,
            (
                resolved_charter_id,
                resolved_reserve,
                payment.amount,
                payment.payment_date,
                payment.payment_method,
                payment.cheque_number,  # Store cheque# in payment_key
                _build_notes(payment),
            ),
        )

        result = cur.fetchone()
        payment_id = result[0]
        created_at = result[1]

        # If it's a cheque, also record in banking_transactions for
        # reconciliation
        if payment.payment_method.lower() == "cheque" and payment.cheque_number:
            cur.execute(
                """
                INSERT INTO banking_transactions (
                    transaction_date,
                    description,
                    credit_amount,
                    debit_amount,
                    vendor_extracted,
                    category,
                    created_at,
                    updated_at
                ) VALUES (
                    %s,
                    %s,
                    %s,
                    0,
                    %s,
                    'Revenue - Charter Income',
                    NOW(),
                    NOW()
                )
                RETURNING transaction_id
            """,
                (
                    payment.payment_date,
                    f"CHEQUE #{payment.cheque_number} - {payment.payer_name}",
                    payment.amount,
                    payment.payer_name,
                ),
            )
            banking_transaction_id = cur.fetchone()[0]
            cur.execute(
                """
                UPDATE payments
                SET banking_transaction_id = %s
                WHERE payment_id = %s
                """,
                (banking_transaction_id, payment_id),
            )

        conn.commit()

        return {
            "success": True,
            "message": "Payment recorded successfully",
            "payment_id": payment_id,
            "amount": payment.amount,
            "payer": payment.payer_name,
            "created_at": created_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}")
    finally:
        cur.close()
        conn.close()


@router.get("/search", response_model=list[ReceivedPaymentResponse])
async def search_received_payments(
    payer_name: str | None = None,
    cheque_number: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    payment_method: str | None = None,
    unallocated_only: bool = False,
    limit: int = 100,
):
    """Search for received payments"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # Build WHERE clause
        where_clauses = []
        params = []

        if payer_name:
            where_clauses.append("p.notes ILIKE %s")
            params.append(f"%{payer_name}%")

        if cheque_number:
            where_clauses.append("p.payment_key = %s")
            params.append(cheque_number)

        if amount_min is not None:
            where_clauses.append("p.amount >= %s")
            params.append(amount_min)

        if amount_max is not None:
            where_clauses.append("p.amount <= %s")
            params.append(amount_max)

        if date_from:
            where_clauses.append("p.payment_date >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("p.payment_date <= %s")
            params.append(date_to)

        if payment_method:
            where_clauses.append("p.payment_method = %s")
            params.append(payment_method)

        if unallocated_only:
            where_clauses.append("p.charter_id IS NULL")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        params.append(limit)

        query = f"""
            SELECT 
                p.payment_id,
                p.amount,
                p.payment_date,
                p.payment_method,
                p.payment_key as cheque_number,
                p.notes,
                p.charter_id,
                'payment' as deposit_type,
                p.created_at,
                COALESCE(c.reserve_number, p.reserve_number) AS reserve_number,
                c.client_display_name as customer_name,
                c.charter_date as charter_date,
                COALESCE(c.total_amount_due, c.grand_total, c.subtotal) as charter_amount
            FROM payments p
            LEFT JOIN charters c ON p.charter_id = c.charter_id
            WHERE {where_sql}
            ORDER BY p.payment_date DESC, p.payment_id DESC
            LIMIT %s
        """

        cur.execute(query, params)
        results = cur.fetchall()

        payments = []
        for row in results:
            payer_name = _extract_note_field(row["notes"], ("Payer:",)) or "Unknown"
            bank_name = _extract_note_field(
                row["notes"],
                (
                    "Bank:",
                    "Bank Name:",
                    "Financial Institution:",
                ),
            )

            payments.append(
                ReceivedPaymentResponse(
                    payment_id=row["payment_id"],
                    amount=float(row["amount"]),
                    payment_date=row["payment_date"],
                    payment_method=row["payment_method"],
                    payer_name=payer_name,
                    cheque_number=row["cheque_number"],
                    bank_name=bank_name,
                    charter_id=row["charter_id"],
                    reserve_number=row["reserve_number"],
                    notes=row["notes"],
                    deposit_type=row["deposit_type"] or "payment",
                    created_at=row["created_at"],
                    customer_name=row["customer_name"],
                    charter_date=row["charter_date"],
                    charter_amount=(
                        float(row["charter_amount"]) if row["charter_amount"] else None
                    ),
                )
            )

        return payments

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}")
    finally:
        cur.close()
        conn.close()


@router.get("/unallocated", response_model=list[ReceivedPaymentResponse])
async def get_unallocated_payments():
    """Get all payments not linked to a charter (need allocation)"""
    return await search_received_payments(unallocated_only=True)


@router.put("/{payment_id}", response_model=dict)
async def update_received_payment(payment_id: int, update: ReceivedPaymentUpdate):
    """Update a received payment"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT notes, payment_key, charter_id, reserve_number
            FROM payments
            WHERE payment_id = %s
            """,
            (payment_id,),
        )
        existing_payment = cur.fetchone()
        if not existing_payment:
            raise HTTPException(
                status_code=404,
                detail=f"Payment {payment_id} not found",
            )

        # Build UPDATE clause
        update_fields = []
        params = []

        if update.amount is not None:
            update_fields.append("amount = %s")
            params.append(update.amount)

        if update.payment_date is not None:
            update_fields.append("payment_date = %s")
            params.append(update.payment_date)

        if update.payment_method is not None:
            update_fields.append("payment_method = %s")
            params.append(update.payment_method)

        if update.cheque_number is not None:
            update_fields.append("payment_key = %s")
            params.append(update.cheque_number)

        resolved_charter_id = existing_payment[2]
        resolved_reserve = existing_payment[3]
        if update.charter_id is not None or update.reserve_number is not None:
            resolved_charter_id, resolved_reserve = _resolve_charter_reference(
                cur,
                update.charter_id,
                update.reserve_number,
            )
            update_fields.append("charter_id = %s")
            params.append(resolved_charter_id)
            update_fields.append("reserve_number = %s")
            params.append(resolved_reserve)

        if (
            update.payer_name is not None
            or update.bank_name is not None
            or update.reserve_number is not None
            or update.notes is not None
        ):
            update_fields.append("notes = %s")
            params.append(
                _updated_notes(
                    existing_payment[0],
                    update,
                    resolved_reserve,
                )
            )

        update_fields.append("last_updated = NOW()")

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        params.append(payment_id)

        update_sql = f"""
            UPDATE payments
            SET {', '.join(update_fields)}
            WHERE payment_id = %s
            RETURNING payment_id, amount, payment_date, payment_method
        """

        cur.execute(update_sql, params)
        result = cur.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")

        conn.commit()

        return {
            "success": True,
            "message": "Payment updated successfully",
            "payment_id": result[0],
            "amount": float(result[1]),
            "payment_date": str(result[2]),
            "payment_method": result[3],
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}")
    finally:
        cur.close()
        conn.close()


@router.delete("/{payment_id}", response_model=dict)
async def delete_received_payment(payment_id: int):
    """Delete a received payment (use cautiously)"""
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Detach dependent links first so legacy "used" payments
        # (e.g., escrow transfers) can still be deleted safely.
        cur.execute(
            """
            UPDATE income_ledger
            SET payment_id = NULL
            WHERE payment_id = %s
            """,
            (payment_id,),
        )
        detached_income_rows = cur.rowcount or 0

        cur.execute(
            """
            UPDATE square_etransfer_reconciliation
            SET square_payment_id = NULL
            WHERE square_payment_id = %s
            """,
            (payment_id,),
        )
        detached_recon_rows = cur.rowcount or 0

        cur.execute(
            """
            DELETE FROM payments
            WHERE payment_id = %s
            RETURNING payment_id, amount
        """,
            (payment_id,),
        )

        result = cur.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")

        conn.commit()

        return {
            "success": True,
            "message": f"Payment ${result[1]:.2f} deleted",
            "payment_id": result[0],
            "detached_income_ledger_rows": int(detached_income_rows),
            "detached_reconciliation_rows": int(detached_recon_rows),
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e!s}")
    finally:
        cur.close()
        conn.close()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _build_notes(payment: ReceivedPaymentCreate) -> str:
    """Build formatted notes string from payment details"""
    parts = [f"Payer: {payment.payer_name}"]

    if payment.cheque_number:
        parts.append(f"Cheque #: {payment.cheque_number}")

    if payment.bank_name:
        parts.append(f"Bank: {payment.bank_name}")

    if payment.reserve_number:
        parts.append(f"Reserve #: {payment.reserve_number}")

    if payment.notes:
        parts.append(f"Notes: {payment.notes}")

    return "\n".join(parts)


def _resolve_charter_reference(
    cur,
    charter_id: int | None,
    reserve_number: str | None,
) -> tuple[int | None, str | None]:
    """Resolve either charter key and guarantee both persisted keys agree."""
    reserve_number = (reserve_number or "").strip() or None
    if charter_id is None and reserve_number is None:
        return None, None

    if charter_id is not None:
        cur.execute(
            """
            SELECT charter_id, reserve_number
            FROM charters
            WHERE charter_id = %s
            """,
            (charter_id,),
        )
    else:
        cur.execute(
            """
            SELECT charter_id, reserve_number
            FROM charters
            WHERE reserve_number = %s
            """,
            (reserve_number,),
        )
    row = cur.fetchone()
    if not row:
        identifier = charter_id if charter_id is not None else reserve_number
        raise HTTPException(
            status_code=404,
            detail=f"Charter {identifier} not found",
        )
    if reserve_number is not None and str(row[1]) != reserve_number:
        raise HTTPException(
            status_code=400,
            detail="charter_id and reserve_number identify different charters",
        )
    return int(row[0]), str(row[1])


def _updated_notes(
    existing_notes: str | None,
    update: ReceivedPaymentUpdate,
    reserve_number: str | None,
) -> str:
    """Rebuild structured received-payment notes without dropping metadata."""
    payer_name = (
        update.payer_name
        if update.payer_name is not None
        else _extract_note_field(existing_notes, ("Payer:",))
    )
    bank_name = (
        update.bank_name
        if update.bank_name is not None
        else _extract_note_field(
            existing_notes,
            ("Bank:", "Bank Name:", "Financial Institution:"),
        )
    )
    free_notes = (
        update.notes
        if update.notes is not None
        else _extract_note_field(existing_notes, ("Notes:",))
    )
    parts = [f"Payer: {payer_name or 'Unknown'}"]
    if bank_name:
        parts.append(f"Bank: {bank_name}")
    if reserve_number:
        parts.append(f"Reserve #: {reserve_number}")
    if free_notes:
        parts.append(f"Notes: {free_notes}")
    return "\n".join(parts)
