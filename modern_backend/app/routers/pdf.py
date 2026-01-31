"""
PDF Generation Endpoints
"""

from fastapi import APIRouter, Path, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from ..db import cursor
from ..services.pdf_generator import generate_charter_pdf

router = APIRouter(prefix="/api", tags=["pdf"])


@router.get("/charters/{charter_id}/invoice-pdf")
def get_charter_invoice_pdf(charter_id: int = Path(...)):
    """Generate and download charter invoice as PDF"""
    
    with cursor() as cur:
        cur.execute("""
            SELECT 
                c.charter_id,
                c.charter_date,
                c.reserve_number,
                c.client_id,
                c.passenger_load,
                c.vehicle,
                c.vehicle_description,
                c.vehicle_type_requested,
                c.driver,
                c.driver_name,
                c.pickup_address,
                c.dropoff_address,
                c.status,
                c.charter_type,
                c.exchange_of_services_details,
                c.gl_revenue_code,
                c.gl_expense_code,
                c.total_amount_due,
                c.paid_amount,
                COALESCE(p.total_paid, 0) AS total_paid,
                (COALESCE(c.total_amount_due, 0) - COALESCE(p.total_paid, 0)) AS balance,
                COALESCE(nrr.nrr_amount, 0) AS nrr_amount,
                cl.client_name,
                cl.company_name,
                cl.email,
                cl.phone,
                v.passenger_capacity,
                CASE 
                    WHEN c.closed = true AND c.cancelled = false THEN 'Reconciled'
                    WHEN c.cancelled = true THEN 'Cancelled'
                    ELSE 'Not Reconciled'
                END AS reconciliation_status
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            LEFT JOIN vehicles v ON c.vehicle_booked_id = v.vehicle_id
            LEFT JOIN (
                SELECT charter_id, SUM(amount) AS total_paid
                FROM payments
                WHERE deleted_at IS NULL
                GROUP BY charter_id
            ) p ON c.charter_id = p.charter_id
            LEFT JOIN (
                SELECT charter_id, SUM(amount) AS nrr_amount
                FROM payments
                WHERE payment_label IN ('NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer')
                AND payment_label NOT IN ('Deposit')
                AND deleted_at IS NULL
                GROUP BY charter_id
            ) nrr ON c.charter_id = nrr.charter_id
            WHERE c.charter_id = %s
        """, (charter_id,))
        
        record = cur.fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Charter not found")
        
        # Map to dict
        columns = [desc[0] for desc in cur.description]
        charter_data = dict(zip(columns, record))
        
        # Handle JSONB
        if isinstance(charter_data.get('exchange_of_services_details'), str):
            import json
            try:
                charter_data['exchange_of_services_details'] = json.loads(charter_data['exchange_of_services_details'])
            except:
                charter_data['exchange_of_services_details'] = {}
        elif not charter_data.get('exchange_of_services_details'):
            charter_data['exchange_of_services_details'] = {}
    
    # Generate PDF
    try:
        pdf_bytes = generate_charter_pdf(charter_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    
    # Return as downloadable file
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=Charter_{charter_data.get('reserve_number', 'Invoice')}.pdf"
        }
    )


@router.get("/charters/{charter_id}/invoice-pdf-preview")
def preview_charter_invoice_pdf(charter_id: int = Path(...)):
    """Preview charter invoice as PDF (inline)"""
    
    with cursor() as cur:
        cur.execute("""
            SELECT 
                c.charter_id,
                c.charter_date,
                c.reserve_number,
                c.client_id,
                c.passenger_load,
                c.vehicle,
                c.vehicle_description,
                c.vehicle_type_requested,
                c.driver,
                c.driver_name,
                c.pickup_address,
                c.dropoff_address,
                c.status,
                c.charter_type,
                c.exchange_of_services_details,
                c.gl_revenue_code,
                c.gl_expense_code,
                c.total_amount_due,
                c.paid_amount,
                COALESCE(p.total_paid, 0) AS total_paid,
                (COALESCE(c.total_amount_due, 0) - COALESCE(p.total_paid, 0)) AS balance,
                COALESCE(nrr.nrr_amount, 0) AS nrr_amount,
                cl.client_name,
                cl.company_name,
                cl.email,
                cl.phone,
                v.passenger_capacity,
                CASE 
                    WHEN c.closed = true AND c.cancelled = false THEN 'Reconciled'
                    WHEN c.cancelled = true THEN 'Cancelled'
                    ELSE 'Not Reconciled'
                END AS reconciliation_status
            FROM charters c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            LEFT JOIN vehicles v ON c.vehicle_booked_id = v.vehicle_id
            LEFT JOIN (
                SELECT charter_id, SUM(amount) AS total_paid
                FROM payments
                WHERE deleted_at IS NULL
                GROUP BY charter_id
            ) p ON c.charter_id = p.charter_id
            LEFT JOIN (
                SELECT charter_id, SUM(amount) AS nrr_amount
                FROM payments
                WHERE payment_label IN ('NRR', 'NRD', 'Non-Refundable Retainer', 'Retainer')
                AND payment_label NOT IN ('Deposit')
                AND deleted_at IS NULL
                GROUP BY charter_id
            ) nrr ON c.charter_id = nrr.charter_id
            WHERE c.charter_id = %s
        """, (charter_id,))
        
        record = cur.fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="Charter not found")
        
        # Map to dict
        columns = [desc[0] for desc in cur.description]
        charter_data = dict(zip(columns, record))
        
        # Handle JSONB
        if isinstance(charter_data.get('exchange_of_services_details'), str):
            import json
            try:
                charter_data['exchange_of_services_details'] = json.loads(charter_data['exchange_of_services_details'])
            except:
                charter_data['exchange_of_services_details'] = {}
        elif not charter_data.get('exchange_of_services_details'):
            charter_data['exchange_of_services_details'] = {}
    
    # Generate PDF
    try:
        pdf_bytes = generate_charter_pdf(charter_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
    
    # Return as inline display
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf"
    )
