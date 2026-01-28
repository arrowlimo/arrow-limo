# LMS vs. New System - Charter Sheet Comparison

## 📋 LMS CHARTER SHEET ANALYSIS (from screenshot)

### Header Information ✅
- Company name, address, contact
- GST # 
- "Reservation Sheet" title

### Customer Details ✅
- Customer name: "Passenger Eagle Builders"
- Address (Box 1690)
- City/State/Zip (Blackfalds, AB, T0M0J0)
- Home/Work/Cell/Fax phones
- Reservation #: 019846
- Date/Time: "Fri 24-2026 Saturday 15:30"
- DO Time, Est Hours (8.50)

### Billing Information ✅
- Bill To, CC Name
- Number (masked ****-2300)
- Expires date
- Type (Visa)
- Agency

### Charter Details ✅
- Account Type: General
- Order By, Order No, Order Phone, Order Date
- # of Passengers: 0
- Vehicle Type: 27 Pass Shuttle Bus
- Vehicle ID: Limo24
- Driver: DR117
- Status indicator

### CHARGES SECTION ✅ (Critical)
```
CHARGES                      RATE      AMOUNT
Service Fee           Flt    1,250.00  1,250.00
Beverage Order        Flt      345.00    345.00
Gratuity              Pct       15.00    202.50
Fuel Surcharge        Pct        3.00     54.88
Concert Special       Flt                  54.88
Wait/Travel Time      Flt
Extra Stops           Flt
Fuel Surcharge        Pct
Extra Gratuity        Flt
Airport Fee           Flt
Parking Fee           Flt
Tolls Fee             Flt
Misc Fee              Flt

Total Charges:                  $1,892.38
-Deposit:                       $1,966.12
-Annual Due:                      $26.26
```

### Trip Sheet Notes Section ✅
- Multiple beverage items listed:
  - "2 x 1 litre Captain Morgan"
  - "1 x 1 ltr corona royal 60"
  - "1 x 12 can crazy larry's hard lemonade 30"
  - "1 x 12 can coors banquet 40"
  - "1 x 12 kitchen canadian 40"
  - "2 x 20oz gingeral 10"
  - "1 x 20oz coke 10"
  - "4 CUTWATER TEQUILA MARGARITA 25"

### Driver Information ❌ (MISSING IN OUR SYSTEM)
- Driver Sped, Time Out, Time In
- Arrived, Drop Off
- Total Hours, Miles In/Out, Total
- Phone In/Out, Total
- Gallons, Price Gal, Total

### Payment Breakdown Section ❌ (CRITICAL MISSING)
**LMS Shows:**
- Payment Type: Visa
- Taken By: Sales

**What's MISSING in our system:**
```
NRD = $500.00 (Non-refundable deposit)
CC = $300.00 (Credit card)
E-Transfer = $250.00
Cash = $150.15
Balance = $0.00
```

---

## 🔍 COMPARISON ANALYSIS

### ✅ WHAT WE HAVE (Working)
1. **Basic charter info**: reserve_number, charter_date, customer, vehicle
2. **Charges line items**: base_rate, airport_fee, additional, gst
3. **Single payment tracking**: amount, payment_method, payment_date
4. **Charter types**: hourly, package, split_run, etc.
5. **Pricing defaults**: by vehicle type
6. **Quote calculator**: 3 quote options
7. **Gratuity**: percentage-based (18% default)
8. **GST exemption**: client-level flag

### ❌ WHAT'S MISSING (Critical Gaps)

#### 1. **PAYMENT BREAKDOWN** (Highest Priority)
**Current:** Single payment record per transaction
```sql
payment_id | reserve_number | amount | payment_method | notes
1234       | 019824        | 75.00  | cash          | Deposit paid at booking
```

**LMS Has:** Multiple payments per charter with labels
```
NRD (Non-Refundable Deposit) = $500.00
CC (Credit Card)             = $300.00
E-Transfer                   = $250.00
Cash                         = $150.15
Total Paid                   = $1,200.15
Balance Due                  = $0.00
```

**Solution Needed:**
- Allow multiple payments per reserve_number ✅ (already supported)
- Add `payment_label` field (NRD, Deposit, Final Payment, etc.)
- Display all payments on charter sheet with labels
- Calculate running balance

#### 2. **DRIVER TRIP LOG FIELDS**
**Missing columns in charters table:**
- `actual_pickup_time` (Time Out)
- `actual_dropoff_time` (Time In)
- `actual_hours` (Total Hours)
- `odometer_start` (Miles In)
- `odometer_end` (Miles Out)
- `total_miles` (calculated)
- `fuel_gallons` (Gallons)
- `fuel_price_per_gallon` (Price Gal)
- `fuel_total_cost` (Total)

#### 3. **DEPOSIT vs ANNUAL DUE CALCULATION**
**LMS Shows:**
```
Total Charges:  $1,892.38
-Deposit:       $1,966.12
-Annual Due:      $26.26 (CREDIT, they overpaid)
```

**Our System:**
- Only tracks `total_amount_due` (total charges)
- Tracks `paid_amount` (sum of payments)
- Missing: Deposit amount separately labeled
- Missing: Credit/balance forward tracking

#### 4. **FUEL SURCHARGE** (Percentage-based)
**LMS Shows:**
```
Fuel Surcharge  Pct  3.00  $54.88
```

**Our System:**
- ✅ Have fuel_surcharge in charge_catalog
- ✅ Marked as percentage-based
- ❌ Currently inactive
- ❌ Not wired into booking form

#### 5. **CONCERT SPECIAL / CUSTOM CHARGES**
**LMS Shows:**
```
Concert Special  Flt  $54.88
```

**Our System:**
- ✅ Have `BASE_CUSTOM` in catalog
- ✅ Have `additional` charge type for misc fees
- Need: Better labeling/description for custom line items

---

## 🔧 REQUIRED FIXES

### Priority 1: Payment Breakdown Display

**Add payment_label column:**
```sql
ALTER TABLE payments 
ADD COLUMN payment_label VARCHAR(50);

-- Examples: 'NRD', 'Deposit', 'Final Payment', 'Balance', etc.
```

**Update payment constraint to include new methods:**
```sql
-- Already have: cash, check, credit_card, debit_card, bank_transfer, trade_of_services
-- Add: e_transfer (electronic transfer)
```

**Example payment records:**
```sql
INSERT INTO payments (reserve_number, amount, payment_method, payment_label, notes)
VALUES 
  ('019846', 500.00, 'credit_card', 'NRD', 'Non-refundable deposit'),
  ('019846', 300.00, 'credit_card', 'Deposit', 'Additional deposit'),
  ('019846', 250.00, 'bank_transfer', 'E-Transfer', 'Electronic transfer'),
  ('019846', 150.15, 'cash', 'Final Payment', 'Cash payment');
```

### Priority 2: Driver Trip Log Fields

**Add to charters table:**
```sql
ALTER TABLE charters ADD COLUMN
  actual_pickup_time TIME,
  actual_dropoff_time TIME,
  actual_hours DECIMAL(5,2),
  odometer_start INTEGER,
  odometer_end INTEGER,
  total_miles INTEGER,
  fuel_gallons DECIMAL(8,2),
  fuel_price_per_gallon DECIMAL(6,2),
  fuel_total_cost DECIMAL(10,2);
```

### Priority 3: Charter Sheet API Endpoint

**Create endpoint:** `GET /api/charters/{reserve_number}/charter-sheet`

**Returns:**
```json
{
  "reservation": {...},
  "customer": {...},
  "charges": [
    {"type": "Service Fee", "rate": 1250.00, "amount": 1250.00},
    {"type": "Beverage Order", "rate": 345.00, "amount": 345.00},
    {"type": "Gratuity (15%)", "rate": "15%", "amount": 202.50},
    {"type": "Fuel Surcharge (3%)", "rate": "3%", "amount": 54.88}
  ],
  "total_charges": 1892.38,
  "payments": [
    {"label": "NRD", "method": "credit_card", "amount": 500.00},
    {"label": "Deposit", "method": "credit_card", "amount": 300.00},
    {"label": "E-Transfer", "method": "bank_transfer", "amount": 250.00},
    {"label": "Final Payment", "method": "cash", "amount": 150.15}
  ],
  "total_paid": 1200.15,
  "balance": 692.23,
  "trip_notes": [...],
  "driver_log": {...}
}
```

---

## 📊 FEATURE PARITY MATRIX

| Feature | LMS | Our System | Status |
|---------|-----|------------|--------|
| **Reservation Info** | ✅ | ✅ | COMPLETE |
| **Customer Details** | ✅ | ✅ | COMPLETE |
| **Billing Info** | ✅ | ✅ | COMPLETE |
| **Charter Type** | ✅ | ✅ | COMPLETE |
| **Charge Line Items** | ✅ | ✅ | COMPLETE |
| **Percentage Charges** | ✅ | ✅ | COMPLETE |
| **GST Calculation** | ✅ | ✅ | COMPLETE |
| **Quote Calculator** | ❌ | ✅ | **BETTER** |
| **Payment Breakdown** | ✅ | ❌ | **MISSING** |
| **Payment Labels** | ✅ | ❌ | **MISSING** |
| **Multiple Payments** | ✅ | ✅ | COMPLETE |
| **Balance Calculation** | ✅ | ✅ | COMPLETE |
| **Driver Trip Log** | ✅ | ❌ | **MISSING** |
| **Odometer Tracking** | ✅ | ❌ | **MISSING** |
| **Fuel Tracking** | ✅ | ❌ | **MISSING** |
| **Trip Notes** | ✅ | ✅ | COMPLETE |
| **Beverage Details** | ✅ | ✅ | COMPLETE |

---

## ✅ IMMEDIATE ACTION ITEMS

1. **Add payment_label column** (5 min)
2. **Add driver trip log columns** (5 min)
3. **Create charter-sheet API endpoint** (30 min)
4. **Update bookings endpoint to accept payment_label** (10 min)
5. **Create payment breakdown component** (1 hour)
6. **Add driver trip log form fields** (1 hour)

**Total Time:** ~3 hours to achieve feature parity with LMS charter sheet

---

## 💡 ENHANCEMENTS (Beyond LMS)

**Our system is BETTER in these areas:**
1. ✅ **Quote Calculator** - LMS doesn't auto-generate 3 quote options
2. ✅ **Pricing Defaults** - Structured table vs. manual entry
3. ✅ **Charter Types** - 8 types with validation vs. freeform
4. ✅ **Charge Catalog** - Reusable templates vs. manual entry each time
5. ✅ **API-First** - Modern REST API vs. desktop-only
6. ✅ **Business Keys** - reserve_number everywhere vs. mixed ID usage

**Keep these advantages while adding missing features!**
