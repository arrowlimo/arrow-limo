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
    """Record a payment received from customer (cheque, cash, e-transfer, etc.)"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Validate charter exists if provided
        if payment.charter_id:
            cur.execute("SELECT charter_id FROM charters WHERE charter_id = %s", (payment.charter_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail=f"Charter {payment.charter_id} not found")
        
        # Insert payment
        cur.execute("""
            INSERT INTO payments (
                charter_id,
                amount,
                payment_date,
                payment_method,
                payment_key,
                notes,
                deposit_type,
                last_updated
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            RETURNING payment_id, created_at
        """, (
            payment.charter_id,
            payment.amount,
            payment.payment_date,
            payment.payment_method,
            payment.cheque_number,  # Store cheque# in payment_key
            _build_notes(payment),
            payment.deposit_type
        ))
        
        result = cur.fetchone()
        payment_id = result['payment_id']
        created_at = result['created_at']
        
        # If it's a cheque, also record in banking_transactions for reconciliation
        if payment.payment_method.lower() == 'cheque' and payment.cheque_number:
            cur.execute("""
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
            """, (
                payment.payment_date,
                f"CHEQUE #{payment.cheque_number} - {payment.payer_name}",
                payment.amount,
                payment.payer_name
            ))
        
        conn.commit()
        
        return {
            "success": True,
            "message": "Payment recorded successfully",
            "payment_id": payment_id,
            "amount": payment.amount,
            "payer": payment.payer_name,
            "created_at": created_at
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
    limit: int = 100
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
                p.deposit_type,
                p.created_at,
                c.reserve_number,
                c.customer_name,
                c.pickup_date as charter_date,
                c.total_amount as charter_amount
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
            # Extract payer name from notes
            payer_name = "Unknown"
            if row['notes']:
                lines = row['notes'].split('\n')
                for line in lines:
                    if line.startswith('Payer:'):
                        payer_name = line.replace('Payer:', '').strip()
                        break
            
            payments.append(ReceivedPaymentResponse(
                payment_id=row['payment_id'],
                amount=float(row['amount']),
                payment_date=row['payment_date'],
                payment_method=row['payment_method'],
                payer_name=payer_name,
                cheque_number=row['cheque_number'],
                bank_name=None,  # TODO: Extract from notes if needed
                charter_id=row['charter_id'],
                reserve_number=row['reserve_number'],
                notes=row['notes'],
                deposit_type=row['deposit_type'] or 'payment',
                created_at=row['created_at'],
                customer_name=row['customer_name'],
                charter_date=row['charter_date'],
                charter_amount=float(row['charter_amount']) if row['charter_amount'] else None
            ))
        
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
        
        if update.charter_id is not None:
            update_fields.append("charter_id = %s")
            params.append(update.charter_id)
        
        if update.notes is not None:
            update_fields.append("notes = %s")
            params.append(update.notes)
        
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
            "payment_method": result[3]
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
        cur.execute("""
            DELETE FROM payments
            WHERE payment_id = %s
            RETURNING payment_id, amount
        """, (payment_id,))
        
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"Payment ${result[1]:.2f} deleted",
            "payment_id": result[0]
        }
        
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
