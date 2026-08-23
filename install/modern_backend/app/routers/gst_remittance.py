"""
GST Remittance Payment Management
Endpoints for tracking GST payments to CRA with support for:
- Manual payment entry (payments at other banks)
- Multi-bank payment tracking
- Banking transaction linkage
- Remittance status tracking
"""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..audit.engine import ensure_audit_storage, record_audit_event
from ..audit.schemas import AuditEvent, AuditEventActor
from ..db import get_connection

router = APIRouter(prefix="/api/gst-remittance", tags=["gst-remittance"])


class GSTRemittanceRequest(BaseModel):
    tax_year: int
    gst_period_month: int
    gst_amount_collected: float
    payment_amount: float = Field(..., description="Amount remitted to CRA")
    payment_date: date
    payment_method: str = Field(
        ...,
        description="'banking_transaction', 'manual_entry', or 'forced_debit'",
    )
    banking_institution: str | None = Field(
        None, description="Bank name if multi-bank payment"
    )
    reference_number: str | None = Field(
        None, description="CRA confirmation, cheque#, or wire reference"
    )
    banking_transaction_id: int | None = None
    notes: str | None = None


class GSTRemittanceResponse(BaseModel):
    gst_payment_id: int
    tax_year: int
    gst_period_month: int
    gst_amount_collected: float
    payment_amount: float
    payment_date: date
    payment_method: str
    banking_institution: str | None
    reference_number: str | None
    remittance_status: str
    created_at: str


def _ensure_gst_tables(conn):
    """Ensure GST tables exist"""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS gst_remittance_payments (
                gst_payment_id BIGSERIAL PRIMARY KEY,
                tax_year INT NOT NULL,
                gst_period_month INT NOT NULL,
                gst_amount_collected DECIMAL(12, 2) NOT NULL,
                payment_amount DECIMAL(12, 2) NOT NULL,
                payment_date DATE NOT NULL,
                payment_method VARCHAR(50) NOT NULL,
                banking_institution VARCHAR(100),
                reference_number VARCHAR(100),
                banking_transaction_id BIGINT,
                remittance_status VARCHAR(50) NOT NULL DEFAULT 'pending',
                notes TEXT,
                created_by VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_by VARCHAR(100),
                updated_at TIMESTAMP DEFAULT NOW(),
                retained_until DATE NOT NULL,
                audit_verified BOOLEAN DEFAULT FALSE,
                audit_verified_by VARCHAR(100),
                audit_verified_date TIMESTAMP,
                UNIQUE (tax_year, gst_period_month)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS gst_collected_by_period (
                gst_period_id BIGSERIAL PRIMARY KEY,
                tax_year INT NOT NULL,
                gst_period_month INT NOT NULL,
                gst_amount_collected DECIMAL(12, 2) NOT NULL DEFAULT 0,
                receipt_count INT DEFAULT 0,
                last_calculated TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (tax_year, gst_period_month)
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


def _audit_actor(request: Request) -> AuditEventActor:
    user = getattr(request.state, "current_user", None) or {}
    return AuditEventActor(
        actor_type="user" if user else "service",
        user_id=str(user.get("user_id") or user.get("employee_id") or "") or None,
        username=user.get("username") or user.get("name"),
        role=user.get("role"),
    )


@router.post("/payments", response_model=GSTRemittanceResponse)
async def create_gst_remittance(
    payload: GSTRemittanceRequest,
    request: Request,
    conn=Depends(get_connection),
):
    """Create or update a GST remittance payment record"""
    _ensure_gst_tables(conn)
    ensure_audit_storage(conn)

    actor = _audit_actor(request)
    username = actor.username or "system"

    # Calculate retained_until: 6 years from end of tax year per Income Tax Act
    retained_until = date(payload.tax_year, 12, 31) + timedelta(days=365 * 6)

    cur = conn.cursor()
    try:
        # Check if payment already exists
        cur.execute(
            """
            SELECT gst_payment_id 
            FROM gst_remittance_payments
            WHERE tax_year = %s AND gst_period_month = %s
            """,
            (payload.tax_year, payload.gst_period_month),
        )
        existing = cur.fetchone()

        if existing:
            # Update existing payment
            cur.execute(
                """
                UPDATE gst_remittance_payments
                SET gst_amount_collected = %s,
                    payment_amount = %s,
                    payment_date = %s,
                    payment_method = %s,
                    banking_institution = %s,
                    reference_number = %s,
                    banking_transaction_id = %s,
                    notes = %s,
                    updated_by = %s,
                    updated_at = NOW(),
                    retained_until = %s
                WHERE tax_year = %s AND gst_period_month = %s
                RETURNING gst_payment_id, created_at
                """,
                (
                    payload.gst_amount_collected,
                    payload.payment_amount,
                    payload.payment_date,
                    payload.payment_method,
                    payload.banking_institution,
                    payload.reference_number,
                    payload.banking_transaction_id,
                    payload.notes,
                    username,
                    retained_until,
                    payload.tax_year,
                    payload.gst_period_month,
                ),
            )
            gst_payment_id = cur.fetchone()[0]
        else:
            # Insert new payment
            cur.execute(
                """
                INSERT INTO gst_remittance_payments
                (tax_year, gst_period_month, gst_amount_collected, payment_amount,
                 payment_date, payment_method, banking_institution, reference_number,
                 banking_transaction_id, notes, created_by, retained_until)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING gst_payment_id, created_at
                """,
                (
                    payload.tax_year,
                    payload.gst_period_month,
                    payload.gst_amount_collected,
                    payload.payment_amount,
                    payload.payment_date,
                    payload.payment_method,
                    payload.banking_institution,
                    payload.reference_number,
                    payload.banking_transaction_id,
                    payload.notes,
                    username,
                    retained_until,
                ),
            )
            gst_payment_id = cur.fetchone()[0]

        # Record audit event
        record_audit_event(
            conn,
            module="gst_remittance",
            entity_type="gst_remittance_payment",
            entity_id=str(gst_payment_id),
            action="upsert",
            actor=actor,
            after_json=payload.dict(),
        )

        conn.commit()

        # Fetch and return the created/updated payment
        cur.execute(
            """
            SELECT gst_payment_id, tax_year, gst_period_month, gst_amount_collected,
                   payment_amount, payment_date, payment_method, banking_institution,
                   reference_number, remittance_status, created_at
            FROM gst_remittance_payments
            WHERE gst_payment_id = %s
            """,
            (gst_payment_id,),
        )
        row = cur.fetchone()
        return GSTRemittanceResponse(
            gst_payment_id=row[0],
            tax_year=row[1],
            gst_period_month=row[2],
            gst_amount_collected=float(row[3]),
            payment_amount=float(row[4]),
            payment_date=row[5],
            payment_method=row[6],
            banking_institution=row[7],
            reference_number=row[8],
            remittance_status=row[9],
            created_at=str(row[10]),
        )

    finally:
        cur.close()


@router.get("/payments")
async def list_gst_remittances(
    tax_year: int | None = None,
    status: str | None = None,
    conn=Depends(get_connection),
):
    """List GST remittance payments with optional filtering"""
    _ensure_gst_tables(conn)
    cur = conn.cursor()
    try:
        query = "SELECT * FROM gst_remittance_payments WHERE 1=1"
        params = []

        if tax_year:
            query += " AND tax_year = %s"
            params.append(tax_year)

        if status:
            query += " AND remittance_status = %s"
            params.append(status)

        query += " ORDER BY tax_year DESC, gst_period_month DESC"

        cur.execute(query, params)
        rows = cur.fetchall()

        return [
            {
                "gst_payment_id": row[0],
                "tax_year": row[1],
                "gst_period_month": row[2],
                "gst_amount_collected": float(row[3]),
                "payment_amount": float(row[4]),
                "payment_date": row[5],
                "payment_method": row[6],
                "banking_institution": row[7],
                "reference_number": row[8],
                "remittance_status": row[10],
                "notes": row[12],
                "created_at": str(row[15]),
            }
            for row in rows
        ]

    finally:
        cur.close()


@router.get("/collected-by-period")
async def get_gst_collected(
    tax_year: int | None = None, conn=Depends(get_connection)
):
    """Get GST collected by period for remittance planning"""
    _ensure_gst_tables(conn)
    cur = conn.cursor()
    try:
        query = """
            SELECT tax_year, gst_period_month, gst_amount_collected, 
                   receipt_count, last_calculated
            FROM gst_collected_by_period
        """
        params = []

        if tax_year:
            query += " WHERE tax_year = %s"
            params.append(tax_year)

        query += " ORDER BY tax_year DESC, gst_period_month DESC"

        cur.execute(query, params)
        rows = cur.fetchall()

        return [
            {
                "tax_year": row[0],
                "gst_period_month": row[1],
                "gst_amount_collected": float(row[2]),
                "receipt_count": row[3],
                "last_calculated": str(row[4]) if row[4] else None,
            }
            for row in rows
        ]

    finally:
        cur.close()


@router.post("/calculate-period")
async def calculate_gst_collected(
    tax_year: int,
    gst_period_month: int,
    conn=Depends(get_connection),
):
    """Calculate GST collected for a specific period from receipts"""
    _ensure_gst_tables(conn)
    cur = conn.cursor()
    try:
        # Calculate from receipts
        cur.execute(
            """
            SELECT COALESCE(SUM(gst_amount), 0) as total_gst, COUNT(*) as receipt_count
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date) = %s
            AND EXTRACT(MONTH FROM receipt_date) = %s
            """,
            (tax_year, gst_period_month),
        )
        gst_total, receipt_count = cur.fetchone()

        # Upsert into gst_collected_by_period
        cur.execute(
            """
            INSERT INTO gst_collected_by_period 
            (tax_year, gst_period_month, gst_amount_collected, receipt_count, last_calculated)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (tax_year, gst_period_month)
            DO UPDATE SET 
                gst_amount_collected = %s,
                receipt_count = %s,
                last_calculated = NOW()
            """,
            (tax_year, gst_period_month, gst_total, receipt_count, gst_total, receipt_count),
        )

        conn.commit()

        return {
            "tax_year": tax_year,
            "gst_period_month": gst_period_month,
            "gst_amount_collected": float(gst_total),
            "receipt_count": receipt_count,
        }

    finally:
        cur.close()
