# Booking Form Implementation - Next Steps Checklist

**Status:** Phase 3 Ready (Backend Implementation)  
**Target:** Complete FastAPI endpoints + database migrations  
**Created:** January 24, 2026

---

## PHASE 3: Backend API Implementation

### Task 3.1: Create Pydantic Models
**Status:** ⏳ TODO  
**Location:** `L:\limo\modern_backend\app\schemas\` (new folder)  
**Files to Create:**
- `booking.py` - ChartRequest, ChartResponse, RouteItem models
- `customer.py` - CustomerCreate, CustomerResponse models
- `payment.py` - PaymentCreate, PaymentResponse models

**Requirements:**
```python
# booking.py should include:
class RouteItem(BaseModel):
    type: str  # pickup, dropoff, stop, return
    address: str
    time24: Optional[str] = None
    
class ChartRequest(BaseModel):
    client_name: str  # required, min_length=2
    phone: str
    email: str
    billing_address: str
    city: str
    province: str
    postal_code: str
    charter_date: date  # required, must be >= today
    pickup_time: time  # required, valid HH:MM
    passenger_load: int  # required, 1-50
    vehicle_type_requested: Optional[str] = None
    vehicle_booked_id: Optional[int] = None
    assigned_driver_id: Optional[int] = None
    itinerary: List[RouteItem]  # required, min 2 items
    customer_notes: Optional[str] = None
    dispatcher_notes: Optional[str] = None
    special_requests: Optional[str] = None
    base_charge: Decimal
    airport_fee: Decimal = Decimal("0.00")
    additional_charges_amount: Decimal = Decimal("0.00")
    total_amount_due: Decimal  # required, > 0
    deposit_paid: Decimal = Decimal("0.00")
    status: str = "Quote"  # Quote, Confirmed, Assigned, In Progress, Completed
    cancellation_reason: Optional[str] = None
    reference_number: Optional[str] = None
    
    @validator('charter_date')
    def validate_date(cls, v):
        if v < date.today():
            raise ValueError('charter_date must be today or later')
        return v
    
    @validator('passenger_load')
    def validate_load(cls, v):
        if not 1 <= v <= 50:
            raise ValueError('passenger_load must be 1-50')
        return v
    
    @validator('total_amount_due')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('total_amount_due must be > 0')
        return v
    
    @validator('itinerary')
    def validate_itinerary(cls, v):
        if len(v) < 2:
            raise ValueError('itinerary must have at least 2 stops')
        return v

class ChartResponse(BaseModel):
    charter_id: int
    reserve_number: str
    status: str
    created_at: datetime
```

**Validation Rules:**
- ✅ All required fields present before insert
- ✅ Dates must be >= today
- ✅ Passenger load 1-50
- ✅ Total amount > 0
- ✅ Itinerary minimum 2 stops
- ✅ Status one of: Quote, Confirmed, Assigned, In Progress, Completed, Cancelled
- ❌ Reject if any FK reference doesn't exist (vehicle_id, driver_id)

---

### Task 3.2: Create FastAPI Endpoints
**Status:** ⏳ TODO  
**Location:** `L:\limo\modern_backend\app\routes\` (or `L:\limo\modern_backend\app\api\`)  
**Files to Create:**
- `charters.py` - Main charter endpoints
- `customers.py` - Customer search endpoints
- `vehicles.py` - Vehicle list endpoints
- `employees.py` - Driver list endpoints

**Endpoint 1: Create Charter**
```python
# POST /api/charters
@router.post("/charters", response_model=ChartResponse, status_code=201)
async def create_charter(request: ChartRequest, db: Session = Depends(get_db)):
    """
    Create new charter booking.
    Returns: {charter_id, reserve_number, status, created_at}
    """
    try:
        # Step 1: Validate customer exists or create new
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
        
        # Step 2: Validate vehicle and driver exist (if provided)
        if request.vehicle_booked_id:
            vehicle = db.query(Vehicle).filter(
                Vehicle.vehicle_id == request.vehicle_booked_id
            ).first()
            if not vehicle:
                raise ValueError(f"Vehicle {request.vehicle_booked_id} not found")
        
        if request.assigned_driver_id:
            driver = db.query(Employee).filter(
                Employee.employee_id == request.assigned_driver_id,
                Employee.role.in_(['driver', 'driver_supervisor'])
            ).first()
            if not driver:
                raise ValueError(f"Driver {request.assigned_driver_id} not found")
        
        # Step 3: Create charter record (without reserve_number initially)
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
            reserve_number=None  # To be filled in step 4
        )
        db.add(charter)
        db.flush()  # Get charter_id
        
        # Step 4: Generate reserve_number using sequence
        # SELECT nextval('reserve_number_seq') or similar
        result = db.execute(text("SELECT nextval('reserve_number_seq')"))
        seq_value = result.scalar()
        reserve_number = f"{seq_value:06d}"  # Zero-padded to 6 digits
        
        charter.reserve_number = reserve_number
        db.add(charter)
        
        # Step 5: Insert itinerary routes (linked by reserve_number)
        for idx, route in enumerate(request.itinerary, start=1):
            route_record = CharterRoute(
                reserve_number=reserve_number,
                route_sequence=idx,
                route_type=route.type,
                address=route.address,
                stop_time=route.time24
            )
            db.add(route_record)
        
        # Step 6: Insert charges/pricing (linked by reserve_number)
        if request.base_charge > 0:
            charge = Charge(
                reserve_number=reserve_number,
                charge_type="base_rate",
                amount=request.base_charge,
                description="Base charge"
            )
            db.add(charge)
        
        if request.airport_fee > 0:
            charge = Charge(
                reserve_number=reserve_number,
                charge_type="airport_fee",
                amount=request.airport_fee,
                description="Airport fee"
            )
            db.add(charge)
        
        if request.additional_charges_amount > 0:
            charge = Charge(
                reserve_number=reserve_number,
                charge_type="additional",
                amount=request.additional_charges_amount,
                description="Additional charges"
            )
            db.add(charge)
        
        # Step 7: Calculate and insert GST
        gst_amount = round(request.total_amount_due * Decimal("0.05") / Decimal("1.05"), 2)
        charge = Charge(
            reserve_number=reserve_number,
            charge_type="gst",
            amount=gst_amount,
            description="GST (Alberta 5%)"
        )
        db.add(charge)
        
        # Step 8: Insert deposit payment if provided
        if request.deposit_paid > 0:
            payment = Payment(
                reserve_number=reserve_number,
                amount=request.deposit_paid,
                payment_date=date.today(),
                payment_method="unknown",  # Could add to request
                description="Deposit payment"
            )
            db.add(payment)
        
        # Step 9: COMMIT all changes
        db.commit()
        db.refresh(charter)
        
        return ChartResponse(
            charter_id=charter.charter_id,
            reserve_number=charter.reserve_number,
            status=charter.status,
            created_at=charter.created_at
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
```

**Endpoint 2: Search Charters**
```python
# GET /api/charters/search?q=&limit=10
@router.get("/charters/search")
async def search_charters(q: str, limit: int = 10, db: Session = Depends(get_db)):
    """
    Search charters by:
    - reserve_number (e.g., "019233")
    - client_name (e.g., "john")
    - charter_date (e.g., "2026-02-15")
    """
    query = db.query(Charter)
    
    if q:
        # Try matching reserve_number
        query = query.filter(
            (Charter.reserve_number.ilike(f"%{q}%")) |
            (Charter.customer.client_name.ilike(f"%{q}%")) |
            (Charter.charter_date.cast(String).ilike(f"%{q}%"))
        )
    
    results = query.limit(limit).all()
    
    return {
        "results": [
            {
                "charter_id": c.charter_id,
                "reserve_number": c.reserve_number,
                "client_name": c.customer.client_name,
                "charter_date": c.charter_date,
                "status": c.status,
                "total_amount_due": str(c.total_amount_due)
            }
            for c in results
        ],
        "count": len(results)
    }
```

**Endpoint 3: Search Customers**
```python
# GET /api/customers/search?q=&limit=10
@router.get("/customers/search")
async def search_customers(q: str, limit: int = 10, db: Session = Depends(get_db)):
    """Autocomplete customer search by name or phone"""
    query = db.query(Customer)
    
    if q:
        query = query.filter(
            (Customer.client_name.ilike(f"%{q}%")) |
            (Customer.phone.ilike(f"%{q}%"))
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
```

**Endpoint 4: List Vehicles**
```python
# GET /api/vehicles
@router.get("/vehicles")
async def list_vehicles(db: Session = Depends(get_db)):
    """List all available vehicles for dropdown"""
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
```

**Endpoint 5: List Drivers**
```python
# GET /api/employees/drivers
@router.get("/employees/drivers")
async def list_drivers(db: Session = Depends(get_db)):
    """List all drivers for dropdown"""
    drivers = db.query(Employee).filter(
        Employee.role.in_(['driver', 'driver_supervisor'])
    ).all()
    
    return {
        "results": [
            {
                "employee_id": e.employee_id,
                "first_name": e.first_name,
                "last_name": e.last_name,
                "driver_license": e.license_number
            }
            for e in drivers
        ],
        "count": len(drivers)
    }
```

---

### Task 3.3: Update FastAPI Router
**Status:** ⏳ TODO  
**Location:** `L:\limo\modern_backend\app\main.py`  
**Action:** Import and register new routers
```python
from app.routes import charters, customers, vehicles, employees

app.include_router(charters.router, prefix="/api", tags=["charters"])
app.include_router(customers.router, prefix="/api", tags=["customers"])
app.include_router(vehicles.router, prefix="/api", tags=["vehicles"])
app.include_router(employees.router, prefix="/api", tags=["employees"])
```

---

## PHASE 4: Database Migrations & Setup

### Task 4.1: Create Reserve Number Sequence
**Status:** ⏳ TODO  
**Execute via:** `psql` or Python script  
**SQL:**
```sql
CREATE SEQUENCE reserve_number_seq
  START WITH 1
  INCREMENT BY 1
  MINVALUE 1
  MAXVALUE 999999
  CACHE 1;

-- Test it:
SELECT nextval('reserve_number_seq');  -- Should return 1, 2, 3, etc.
```

### Task 4.2: Add Missing Constraints
**Status:** ⏳ TODO  
**Verify in PostgreSQL:**
```sql
-- 1. Unique constraint on reserve_number
ALTER TABLE charters ADD CONSTRAINT uq_charters_reserve_number 
UNIQUE (reserve_number);

-- 2. Foreign keys for vehicle & driver
ALTER TABLE charters ADD CONSTRAINT fk_charters_vehicle 
FOREIGN KEY (vehicle_booked_id) REFERENCES vehicles(vehicle_id);

ALTER TABLE charters ADD CONSTRAINT fk_charters_driver 
FOREIGN KEY (assigned_driver_id) REFERENCES employees(employee_id);

-- 3. Check constraint for passenger_load
ALTER TABLE charters ADD CONSTRAINT ck_charters_passenger_load 
CHECK (passenger_load >= 1 AND passenger_load <= 50);

-- 4. Check constraint for valid status
ALTER TABLE charters ADD CONSTRAINT ck_charters_status 
CHECK (status IN ('Quote', 'Confirmed', 'Assigned', 'In Progress', 'Completed', 'Cancelled'));
```

### Task 4.3: Add Indexes for Performance
**Status:** ⏳ TODO  
**Execute:**
```sql
-- Speed up searches by reserve_number
CREATE INDEX idx_charters_reserve_number ON charters(reserve_number);
CREATE INDEX idx_charter_routes_reserve_number ON charter_routes(reserve_number);
CREATE INDEX idx_charges_reserve_number ON charges(reserve_number);
CREATE INDEX idx_payments_reserve_number ON payments(reserve_number);

-- Speed up searches by customer
CREATE INDEX idx_charters_customer_id ON charters(customer_id);
CREATE INDEX idx_customers_client_name ON customers(client_name);
```

---

## PHASE 5: Testing & Validation

### Task 5.1: Unit Tests
**Status:** ⏳ TODO  
**Location:** `L:\limo\modern_backend\tests\`  
**Test Cases:**
- ✅ POST /api/charters with valid data → returns 201
- ✅ POST /api/charters with missing required field → returns 400
- ✅ POST /api/charters with passenger_load > 50 → returns 400
- ✅ POST /api/charters with date in past → returns 400
- ✅ GET /api/charters/search → returns matching charters
- ✅ GET /api/customers/search → returns matching customers
- ✅ GET /api/vehicles → returns all vehicles
- ✅ GET /api/employees/drivers → returns all drivers
- ✅ Reserve number is generated and unique
- ✅ Itinerary routes inserted correctly (ordered by sequence)
- ✅ Charges inserted correctly (base + airport + additional + GST)
- ✅ Payment inserted if deposit provided
- ✅ All ForeignKey relationships validated

### Task 5.2: Integration Tests (End-to-End)
**Status:** ⏳ TODO  
**Test Flow:**
1. Create charter via API
2. Verify charter_id returned
3. Verify reserve_number generated (6-digit format)
4. Query charters table → verify record exists
5. Query charter_routes table → verify itinerary inserted (2+ rows, ordered)
6. Query charges table → verify pricing inserted (base + airport + GST)
7. Query payments table → verify deposit inserted
8. Update charter status (Quote → Confirmed)
9. Verify all updated correctly
10. Delete charter (soft delete or archive)

### Task 5.3: Vue Component Integration Test
**Status:** ⏳ TODO  
**Test Scenarios:**
- ✅ Form loads with empty fields
- ✅ Customer autocomplete shows suggestions
- ✅ Add stop button adds new row
- ✅ Remove stop button deletes row
- ✅ Pricing auto-calculates on each change
- ✅ GST formula correct: gst = total * 0.05 / 1.05
- ✅ Form validation prevents submission with errors
- ✅ Submit button disabled during API call
- ✅ Success message shows with reserve_number
- ✅ Form clears after successful submission

### Task 5.4: Database Integrity Test
**Status:** ⏳ TODO  
**Queries to Run:**
```sql
-- 1. Verify no duplicate reserve_numbers
SELECT reserve_number, COUNT(*) 
FROM charters 
GROUP BY reserve_number 
HAVING COUNT(*) > 1;
-- Result should be: (empty - no duplicates)

-- 2. Verify all charters have reserve_number
SELECT COUNT(*) FROM charters WHERE reserve_number IS NULL;
-- Result should be: 0

-- 3. Verify itinerary has minimum 2 stops per charter
SELECT c.reserve_number, COUNT(cr.route_id) as route_count
FROM charters c
LEFT JOIN charter_routes cr ON c.reserve_number = cr.reserve_number
GROUP BY c.reserve_number
HAVING COUNT(cr.route_id) < 2;
-- Result should be: (empty - all have 2+ stops)

-- 4. Verify GST calculations
SELECT 
  c.reserve_number,
  c.total_amount_due,
  COALESCE(SUM(ch.amount) FILTER (WHERE ch.charge_type = 'gst'), 0) as gst_stored,
  ROUND(c.total_amount_due * 0.05 / 1.05, 2) as gst_expected,
  CASE 
    WHEN COALESCE(SUM(ch.amount) FILTER (WHERE ch.charge_type = 'gst'), 0) = 
         ROUND(c.total_amount_due * 0.05 / 1.05, 2) THEN 'OK'
    ELSE 'ERROR'
  END as gst_status
FROM charters c
LEFT JOIN charges ch ON c.reserve_number = ch.reserve_number
GROUP BY c.reserve_number, c.total_amount_due
ORDER BY gst_status DESC;
```

---

## PHASE 6: Documentation & Handoff

### Task 6.1: API Documentation
**Status:** ⏳ TODO  
**Generate:** FastAPI auto-generates at `http://127.0.0.1:8000/docs` (Swagger UI)  
**Manual:** Create `BOOKING_API_ENDPOINTS.md` with all request/response examples

### Task 6.2: Deployment Checklist
**Status:** ⏳ TODO  
**Items:**
- ✅ All tests pass (unit + integration)
- ✅ API docs generated and reviewed
- ✅ Database migrations applied
- ✅ Vue component bundled in frontend build
- ✅ Environment variables set (DB connection string, API host)
- ✅ CORS configured for frontend → backend communication
- ✅ Error handling implemented and tested
- ✅ Logging added for debugging
- ✅ Performance tested (response time < 500ms for list queries)

---

## SUCCESS CRITERIA (Definition of Done)

**Form Creation:**
- ✅ User can fill all 7 form sections
- ✅ Form validates client-side before submission
- ✅ Submit button disabled during API call
- ✅ Success message shows reserve_number

**Backend API:**
- ✅ All 5 endpoints respond with correct status codes (200, 201, 400)
- ✅ All data validated (Pydantic models)
- ✅ All relationships created (FK constraints)
- ✅ Reserve numbers generated uniquely (6-digit format)
- ✅ All transactions committed to database

**Database:**
- ✅ Charters table has new records
- ✅ Charter_routes table has itinerary stops (2+ per charter, ordered)
- ✅ Charges table has pricing line items (base + airport + GST)
- ✅ Payments table has deposit payments
- ✅ All foreign key relationships intact
- ✅ No duplicate reserve_numbers

**User Experience:**
- ✅ Form loads in < 2 seconds
- ✅ Autocomplete responds in < 1 second
- ✅ Submit processes in < 3 seconds
- ✅ Error messages clear and actionable
- ✅ Success message shows reserve_number for user confirmation

---

## ESTIMATED TIMELINE

| Phase | Task | Duration | Notes |
|-------|------|----------|-------|
| 3.1 | Pydantic Models | 1-2 hours | Copy from mapping doc, add validators |
| 3.2 | FastAPI Endpoints | 3-4 hours | 5 endpoints × 40 min each |
| 3.3 | Router Registration | 30 min | 5 imports + registration calls |
| 4.1 | Reserve Sequence | 15 min | Single SQL command |
| 4.2 | Constraints | 30 min | 4 ALTER TABLE commands |
| 4.3 | Indexes | 30 min | 4 CREATE INDEX commands |
| 5.1 | Unit Tests | 3-4 hours | ~15 test cases |
| 5.2 | Integration Tests | 2-3 hours | End-to-end scenarios |
| 5.3 | Vue Tests | 1-2 hours | Manual testing or Jest |
| 5.4 | DB Integrity | 1 hour | SQL verification queries |
| **TOTAL** | **All Phases** | **~16-20 hours** | Can be parallelized |

---

## QUICK START (Today)

1. **Read:** `L:\limo\docs\LMS_TO_POSTGRESQL_BOOKING_MAPPING.md` (15 min)
2. **Read:** `L:\limo\docs\BOOKING_FORM_ARCHITECTURE_DIAGRAMS.md` (15 min)
3. **Create:** Pydantic models file (1 hour)
4. **Create:** First endpoint (POST /api/charters) (1.5 hours)
5. **Test:** POST with curl or Postman (30 min)

**By end of today:** Reserve number generation working + one charter insertable via API

---

**Version:** 1.0  
**Status:** Ready for Implementation  
**Last Updated:** January 24, 2026
