"""
FastAPI routes for charter/booking operations.

Implements 5 main endpoints:
1. POST /api/charters - Create new booking
2. GET /api/charters/search - Search charters
3. GET /api/customers/search - Autocomplete customers
4. GET /api/vehicles - List vehicles
5. GET /api/employees/drivers - List drivers
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, String, cast

from app.database import get_db
from app.models import (
    Charter, CharterRoute, Charge, Payment, Customer, Vehicle, Employee
)
from app.schemas.booking import (
    ChartRequest, ChartResponse, CharterSearch, CustomerSearch,
    VehicleResponse, DriverResponse, ErrorResponse,
    calculate_gst, CHARGE_TYPE_BASE, CHARGE_TYPE_AIRPORT,
    CHARGE_TYPE_ADDITIONAL, CHARGE_TYPE_GST
)

router = APIRouter()


# =============================================================================
# ENDPOINT 1: POST /api/charters - Create New Charter Booking
# =============================================================================

@router.post("/charters", response_model=ChartResponse, status_code=201)
async def create_charter(request: ChartRequest, db: Session = Depends(get_db)):
    """
    Create new charter booking.
    
    This is the most complex endpoint as it:
    1. Validates/creates customer record
    2. Validates vehicle and driver exist (if provided)
    3. Creates charter record
    4. Generates reserve_number via sequence
    5. Inserts itinerary routes (charter_routes)
    6. Inserts pricing line items (charges)
    7. Inserts deposit payment (if provided)
    8. COMMITS all changes atomically
    
    Returns:
        ChartResponse with charter_id, reserve_number, status, created_at
    
    Raises:
        HTTPException 400: Validation error
        HTTPException 500: Database error
    """
    try:
        # ===== STEP 1: Validate or create customer =====
        customer = db.query(Customer).filter(
            Customer.client_name == request.client_name,
            Customer.phone == request.phone
        ).first()
        
        if not customer:
            customer = Customer(
                client_name=request.client_name,
                phone=request.phone,
                email=request.email,
                billing_address=request.billing_address,
                city=request.city,
                province=request.province,
                postal_code=request.postal_code
            )
            db.add(customer)
            db.flush()  # Get customer_id before next inserts
        
        # ===== STEP 2: Validate vehicle exists (if provided) =====
        if request.vehicle_booked_id:
            vehicle = db.query(Vehicle).filter(
                Vehicle.vehicle_id == request.vehicle_booked_id
            ).first()
            if not vehicle:
                raise HTTPException(
                    status_code=400,
                    detail=f"Vehicle ID {request.vehicle_booked_id} not found"
                )
        
        # ===== STEP 3: Validate driver exists (if provided) =====
        if request.assigned_driver_id:
            driver = db.query(Employee).filter(
                Employee.employee_id == request.assigned_driver_id
            ).first()
            if not driver:
                raise HTTPException(
                    status_code=400,
                    detail=f"Driver ID {request.assigned_driver_id} not found"
                )
        
        # ===== STEP 4: Create charter record (without reserve_number initially) =====
        charter = Charter(
            customer_id=customer.client_id,
            charter_date=request.charter_date,
            pickup_time=request.pickup_time,
            passenger_load=request.passenger_load,
            vehicle_type_requested=request.vehicle_type_requested,
            vehicle_booked_id=request.vehicle_booked_id,
            assigned_driver_id=request.assigned_driver_id,
            total_amount_due=request.total_amount_due,
            status=request.status,
            customer_notes=request.customer_notes,
            dispatcher_notes=request.dispatcher_notes,
            special_requests=request.special_requests,
            reference_number=request.reference_number,
            reserve_number=None  # To be filled in step 5
        )
        db.add(charter)
        db.flush()  # Get charter_id
        
        # ===== STEP 5: Generate reserve_number using database sequence =====
        # PostgreSQL sequence: SELECT nextval('reserve_number_seq')
        result = db.execute(text("SELECT nextval('reserve_number_seq')"))
        seq_value = result.scalar()
        reserve_number = f"{seq_value:06d}"  # Zero-padded to 6 digits (e.g., "019233")
        
        charter.reserve_number = reserve_number
        db.add(charter)
        
        # ===== STEP 6: Insert itinerary routes (linked by reserve_number) =====
        # Each stop becomes a separate row in charter_routes, ordered by sequence
        for idx, route in enumerate(request.itinerary, start=1):
            route_record = CharterRoute(
                reserve_number=reserve_number,
                route_sequence=idx,
                route_type=route.type,
                address=route.address,
                stop_time=route.time24
            )
            db.add(route_record)
        
        # ===== STEP 7: Insert charges/pricing (linked by reserve_number) =====
        # Pricing is stored as line items in charges table
        if request.base_charge > 0:
            charge = Charge(
                reserve_number=reserve_number,
                charge_type=CHARGE_TYPE_BASE,
                amount=request.base_charge,
                description="Base charge"
            )
            db.add(charge)
        
        if request.airport_fee > 0:
            charge = Charge(
                reserve_number=reserve_number,
                charge_type=CHARGE_TYPE_AIRPORT,
                amount=request.airport_fee,
                description="Airport fee"
            )
            db.add(charge)
        
        if request.additional_charges_amount > 0:
            charge = Charge(
                reserve_number=reserve_number,
                charge_type=CHARGE_TYPE_ADDITIONAL,
                amount=request.additional_charges_amount,
                description="Additional charges"
            )
            db.add(charge)
        
        # ===== STEP 8: Calculate and insert GST =====
        # GST is tax-included (5% Alberta): gst = total * 0.05 / 1.05
        gst_amount = calculate_gst(request.total_amount_due)
        charge = Charge(
            reserve_number=reserve_number,
            charge_type=CHARGE_TYPE_GST,
            amount=gst_amount,
            description="GST (Alberta 5%, tax-included)"
        )
        db.add(charge)
        
        # ===== STEP 9: Insert deposit payment (if provided) =====
        if request.deposit_paid and request.deposit_paid > 0:
            payment = Payment(
                reserve_number=reserve_number,
                amount=request.deposit_paid,
                payment_date=date.today(),
                payment_method="deposit",
                description="Deposit payment"
            )
            db.add(payment)
        
        # ===== STEP 10: COMMIT all changes atomically =====
        db.commit()
        db.refresh(charter)
        
        return ChartResponse(
            charter_id=charter.charter_id,
            reserve_number=charter.reserve_number,
            status=charter.status,
            created_at=charter.created_at
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        # Rollback on any database error
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create charter: {str(e)}"
        )


# =============================================================================
# ENDPOINT 2: GET /api/charters/search - Search Charters
# =============================================================================

@router.get("/charters/search")
async def search_charters(
    q: str = Query("", description="Search term (reserve#, name, date)"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Search charters by:
    - reserve_number (e.g., "019233")
    - client_name (e.g., "john")
    - charter_date (e.g., "2026-02-15")
    
    Returns list of matching charters with limited fields.
    """
    try:
        query = db.query(
            Charter.charter_id,
            Charter.reserve_number,
            Customer.client_name,
            Charter.charter_date,
            Charter.status,
            Charter.total_amount_due
        ).join(Customer, Charter.customer_id == Customer.client_id)
        
        if q:
            # Search across multiple fields
            search_term = f"%{q}%"
            query = query.filter(
                (Charter.reserve_number.ilike(search_term)) |
                (Customer.client_name.ilike(search_term)) |
                (cast(Charter.charter_date, String).ilike(search_term))
            )
        
        results = query.limit(limit).all()
        
        return {
            "results": [
                {
                    "charter_id": r[0],
                    "reserve_number": r[1],
                    "client_name": r[2],
                    "charter_date": r[3].isoformat() if r[3] else None,
                    "status": r[4],
                    "total_amount_due": str(r[5])
                }
                for r in results
            ],
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Search failed: {str(e)}"
        )


# =============================================================================
# ENDPOINT 3: GET /api/customers/search - Search/Autocomplete Customers
# =============================================================================

@router.get("/customers/search")
async def search_customers(
    q: str = Query("", description="Search term (name, phone)"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Search customers by name or phone for autocomplete dropdown.
    
    Returns list of matching customers with contact info.
    """
    try:
        query = db.query(Customer)
        
        if q:
            search_term = f"%{q}%"
            query = query.filter(
                (Customer.client_name.ilike(search_term)) |
                (Customer.phone.ilike(search_term))
            )
        
        results = query.limit(limit).all()
        
        return {
            "results": [
                {
                    "client_id": c.client_id,
                    "client_name": c.client_name,
                    "phone": c.phone,
                    "email": c.email
                }
                for c in results
            ],
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Search failed: {str(e)}"
        )


# =============================================================================
# ENDPOINT 4: GET /api/vehicles - List All Vehicles
# =============================================================================

@router.get("/vehicles", response_model=dict)
async def list_vehicles(db: Session = Depends(get_db)):
    """
    List all available vehicles for dropdown selection in form.
    
    Returns all vehicles with capacity and details.
    """
    try:
        vehicles = db.query(Vehicle).all()
        
        return {
            "results": [
                {
                    "vehicle_id": v.vehicle_id,
                    "vehicle_number": v.vehicle_number,
                    "make": v.make,
                    "model": v.model,
                    "year": v.year,
                    "passenger_capacity": v.passenger_capacity
                }
                for v in vehicles
            ],
            "count": len(vehicles)
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to list vehicles: {str(e)}"
        )


# =============================================================================
# ENDPOINT 5: GET /api/employees/drivers - List All Drivers
# =============================================================================

@router.get("/employees/drivers", response_model=dict)
async def list_drivers(db: Session = Depends(get_db)):
    """
    List all drivers for dropdown selection in form.
    
    Returns drivers with license info.
    """
    try:
        # Query employees with role = 'driver' or 'driver_supervisor'
        drivers = db.query(Employee).filter(
            Employee.role.in_(['driver', 'driver_supervisor'])
        ).all()
        
        return {
            "results": [
                {
                    "employee_id": d.employee_id,
                    "first_name": d.first_name,
                    "last_name": d.last_name,
                    "driver_license": d.license_number
                }
                for d in drivers
            ],
            "count": len(drivers)
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to list drivers: {str(e)}"
        )


# =============================================================================
# ADDITIONAL HELPER ENDPOINTS (Optional)
# =============================================================================

@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
