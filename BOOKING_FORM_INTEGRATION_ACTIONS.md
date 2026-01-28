# 🚨 IMMEDIATE ACTION ITEMS - Booking Form Integration

**Priority:** HIGH  
**Time Estimate:** 2-3 hours to completion  
**Start:** Now

---

## ✅ ACTION 1: Register New Routes in FastAPI (15 min)

**File:** `L:\limo\modern_backend\app\main.py`

**Current State:**
```python
from .routers import charters as charters_router
app.include_router(charters_router.router)
```

**Problem:** 
- New booking.py router is NOT imported or registered
- New form endpoints (POST /api/charters, GET /api/charters/search, etc.) won't work

**Action Required:**
Add these lines to main.py imports section:
```python
from .routers import booking as booking_router  # NEW LINE
```

Add this line to router registration section:
```python
app.include_router(booking_router.router)  # NEW LINE - add after charters_router
```

**File Location:** `L:\limo\modern_backend\app\main.py` (around line 9-11 for imports, line 120+ for registration)

**Verification:**
After change, run:
```
curl http://127.0.0.1:8000/api/charters/search?q=test
```

Should return JSON with `{"results": [...], "count": X}` (may be empty list if no charters)

---

## ⚠️ ACTION 2: Verify Database Schema (15 min)

**Purpose:** Ensure database has all required columns

**Check 1: charter_routes table**
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'charter_routes' 
ORDER BY ordinal_position;
```

**Expected columns:**
- ✅ `route_id` (PK)
- ✅ `charter_id` or `reserve_number` (FK)
- ❓ `directions` OR `address` (needed)
- ✅ `route_sequence`
- ✅ `route_type`
- ✅ `stop_time`

**If only `directions` exists:**
```sql
-- Add 'address' column
ALTER TABLE charter_routes 
ADD COLUMN address VARCHAR(255) NULL;

-- Migrate data
UPDATE charter_routes 
SET address = directions 
WHERE address IS NULL;
```

**Check 2: charters table**
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'charters' 
ORDER BY ordinal_position;
```

**Expected columns for new form:**
- ✅ `charter_id` (PK)
- ✅ `customer_id` or `client_id` (FK to customers/clients)
- ✅ `reserve_number` (UNIQUE, 6-digit)
- ✅ `charter_date`
- ✅ `pickup_time`
- ✅ `passenger_load`
- ✅ `vehicle_booked_id`
- ✅ `assigned_driver_id`
- ✅ `total_amount_due`
- ✅ `status`
- ❓ `customer_notes`
- ❓ `dispatcher_notes`
- ❓ `special_requests`
- ✅ `created_at`

**If any missing:**
```sql
ALTER TABLE charters
ADD COLUMN customer_notes TEXT NULL,
ADD COLUMN dispatcher_notes TEXT NULL,
ADD COLUMN special_requests TEXT NULL;
```

**Check 3: charges table**
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'charges' 
ORDER BY ordinal_position;
```

**Expected columns:**
- ✅ `charge_id` (PK)
- ✅ `reserve_number` (FK to charters)
- ✅ `charge_type` (base_rate, airport_fee, additional, gst)
- ✅ `amount` (DECIMAL)
- ✅ `description`

**If missing:**
```sql
CREATE TABLE IF NOT EXISTS charges (
  charge_id SERIAL PRIMARY KEY,
  reserve_number VARCHAR(6) NOT NULL REFERENCES charters(reserve_number),
  charge_type VARCHAR(50) NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  description VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Check 4: payments table**
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'payments' 
ORDER BY ordinal_position;
```

**Expected columns:**
- ✅ `payment_id` (PK)
- ✅ `reserve_number` (FK to charters) ⭐ **CRITICAL** - must use reserve_number NOT charter_id
- ✅ `amount` (DECIMAL)
- ✅ `payment_date` (DATE)
- ✅ `payment_method`
- ✅ `description`

---

## ✅ ACTION 3: Create PostgreSQL Sequence (10 min)

**Purpose:** Auto-generate reserve numbers (6-digit format)

**Check if sequence exists:**
```sql
SELECT * FROM information_schema.sequences 
WHERE sequence_name = 'reserve_number_seq';
```

**If NOT found, create it:**
```sql
CREATE SEQUENCE reserve_number_seq
  START WITH 1
  INCREMENT BY 1
  MINVALUE 1
  MAXVALUE 999999
  CACHE 1;
```

**Verify:**
```sql
SELECT nextval('reserve_number_seq');  -- Should return 1
SELECT nextval('reserve_number_seq');  -- Should return 2
```

---

## ⚠️ ACTION 4: Handle POST /api/charters Endpoint Conflict (1 hour)

**Problem:**
- TWO `/api/charters` endpoints exist now:
  - `app/routers/charters.py` (OLD - expects `client_id`, `driver_name` as text)
  - `app/routers/booking.py` (NEW - expects `client_name`, `assigned_driver_id`)
- FastAPI will use whichever is registered LAST (last one wins)
- This creates a conflict

**Solution Options:**

### Option A: Rename New Endpoint (RECOMMENDED for safety)
Change `booking.py` router prefix to:
```python
router = APIRouter(prefix="/api/bookings", tags=["bookings"])
```

Then:
- New form calls: `POST /api/bookings/create` (or similar)
- Old form calls: `POST /api/charters` (unchanged)
- No conflict

**File to modify:** `L:\limo\modern_backend\app\routers/booking.py` line 150+

**Update in BookingFormLMS.vue:** Change submitForm endpoint:
```javascript
const res = await fetch('/api/bookings/create', {  // Changed from /api/charters
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
})
```

### Option B: Merge Both Schemas (BEST for long-term)
Modify the endpoint to detect which schema is being sent:
```python
@router.post("/charters")
async def create_charter(request: dict, db: Session = Depends(get_db)):
    if 'client_name' in request:  # NEW schema
        return create_charter_new_schema(request, db)
    else:  # OLD schema
        return create_charter_old_schema(request, db)
```

This requires more work but enables true backward compatibility.

### Option C: Replace Old Completely (BREAKING CHANGE - risky)
Delete/rename `app/routers/charters.py` POST endpoint, replace with new one
- Risk: Any code calling old endpoint breaks
- Benefit: Single source of truth

**Recommendation:** Start with **Option A** (safest), move to **Option B** later

---

## ✅ ACTION 5: Test All Endpoints (30 min)

**Start backend:**
```powershell
cd L:\limo
python -m uvicorn modern_backend.app.main:app --host 127.0.0.1 --port 8000
```

**Test each endpoint:**

**1. Health Check:**
```bash
curl http://127.0.0.1:8000/health
# Expected: {"status": "ok"}
```

**2. Vehicles List:**
```bash
curl http://127.0.0.1:8000/api/vehicles
# Expected: {"results": [...], "count": X}
```

**3. Drivers List:**
```bash
curl http://127.0.0.1:8000/api/employees/drivers
# Expected: {"results": [...], "count": X}
```

**4. Customer Search:**
```bash
curl "http://127.0.0.1:8000/api/customers/search?q=john"
# Expected: {"results": [...], "count": X}
```

**5. Charter Search:**
```bash
curl "http://127.0.0.1:8000/api/charters/search?q=test"
# Expected: {"results": [...], "count": X}
```

**6. Create Charter (THE BIG ONE):**
```bash
curl -X POST http://127.0.0.1:8000/api/charters \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "John Doe",
    "phone": "403-555-1234",
    "email": "john@example.com",
    "billing_address": "123 Main St",
    "city": "Red Deer",
    "province": "AB",
    "postal_code": "T4N 1A1",
    "charter_date": "2026-02-15",
    "pickup_time": "14:00",
    "passenger_load": 4,
    "itinerary": [
      {"type": "pickup", "address": "Hotel Red Deer", "time24": "14:00"},
      {"type": "dropoff", "address": "Airport YYC", "time24": "16:00"}
    ],
    "base_charge": 150.00,
    "total_amount_due": 175.00,
    "status": "Quote"
  }'
  
# Expected: 201 Created
# Response: {"charter_id": X, "reserve_number": "XXXXXX", "status": "Quote", "created_at": "..."}
```

---

## ✅ ACTION 6: Create BookingPage.vue (1 hour)

**File:** `L:\limo\frontend\src\views\BookingPage.vue`

**Content:**
```vue
<template>
  <div class="booking-page">
    <div class="page-header">
      <h1>🆕 Create New Booking</h1>
      <p>Fill out the form below to create a new charter booking or quote.</p>
    </div>
    
    <div class="page-content">
      <BookingFormLMS />
    </div>
  </div>
</template>

<script setup>
import BookingFormLMS from '@/components/BookingFormLMS.vue'
</script>

<style scoped>
.booking-page {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
  border-bottom: 2px solid #1976d2;
  padding-bottom: 1rem;
}

.page-header h1 {
  margin: 0;
  color: #1976d2;
}

.page-header p {
  margin: 0.5rem 0 0 0;
  color: #666;
  font-size: 1.1rem;
}

.page-content {
  background: #f9f9f9;
  padding: 2rem;
  border-radius: 8px;
}
</style>
```

**Then add route in** `L:\limo\frontend\src\router.js`:

```javascript
import BookingPage from './views/BookingPage.vue'

// Add to routes array:
{ path: '/booking', component: BookingPage },
```

---

## ✅ ACTION 7: Update BookingFormLMS.vue Endpoints (if needed)

**Check current endpoints in BookingFormLMS.vue:**

1. Line ~100: `searchExisting()` - calls what?
   - Should call: `GET /api/charters/search?q=...` ✅
   
2. Line ~120: `applyDuplicate()` - calls what?
   - Should call: `GET /api/charters/{id}` ✅
   
3. Line ~150: `onClientInput()` - calls what?
   - Should call: `GET /api/customers/search?q=...` ✅
   
4. Line ~300: `loadVehiclesAndDrivers()` - calls what?
   - Should call: `GET /api/vehicles` and `GET /api/employees/drivers` ✅
   
5. Line ~500: `submitForm()` - calls what?
   - Should call: `POST /api/charters` or `POST /api/bookings/create` (based on your choice in Action 4)

---

## 🎯 COMPLETION CHECKLIST

Use this checklist to track progress:

- [ ] **Action 1:** Register booking.py router in main.py
- [ ] **Action 2:** Verify database schema (run all 4 checks)
- [ ] **Action 3:** Create reserve_number_seq if needed
- [ ] **Action 4:** Resolve endpoint conflict (choose Option A, B, or C)
- [ ] **Action 5:** Test all 6 endpoints with curl
- [ ] **Action 6:** Create BookingPage.vue component
- [ ] **Action 7:** Verify BookingFormLMS.vue uses correct endpoints
- [ ] **Final Test:** Open http://127.0.0.1:3000/booking and try creating a test booking

---

## 📞 TROUBLESHOOTING

**If POST /api/charters returns 404:**
- ✓ Check: Is booking.py router registered in main.py?
- ✓ Check: Is endpoint decorated with @router.post()?
- ✓ Check: Is app running? (restart if modified main.py)

**If POST /api/charters returns 400 - Validation Error:**
- ✓ Check: Are all required fields in payload?
- ✓ Check: Is charter_date in YYYY-MM-DD format?
- ✓ Check: Is pickup_time in HH:MM format?
- ✓ Check: Does itinerary have at least 2 stops?
- ✓ Check: Is total_amount_due > 0?

**If POST /api/charters returns 400 - Database Error:**
- ✓ Check: Does reserve_number_seq exist?
- ✓ Check: Does customers table exist?
- ✓ Check: Does charges table exist?
- ✓ Check: Does payments table exist?

**If endpoints return 405 Method Not Allowed:**
- ✓ Check: Are you using correct HTTP method? (POST for create, GET for search)
- ✓ Check: Is endpoint path correct?

---

**Estimated Total Time:** 2-3 hours  
**Status:** Ready to execute  
**Start:** Immediately (or whenever user is ready)
