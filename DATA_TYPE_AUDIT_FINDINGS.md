# DATA TYPE AUDIT RESULTS

## Summary of Problems Found

### 🔴 CRITICAL ISSUES

#### 1. **ID Columns Stored as TEXT (20 found)**
- `banking_transactions.transaction_uid` = VARCHAR (should be BIGINT)
- `charter_payments.charter_id` = VARCHAR (should be INTEGER)
- `square_payment_id` fields = VARCHAR (should be BIGINT)

**Impact:** 
- Slower queries (text comparison vs numeric)
- Storage waste (VARCHAR takes more space than INT)
- Can't use numeric functions
- Risk of accidental type casting bugs

**Example problem:**
```python
# If transaction_uid is TEXT "001234"
SELECT * FROM banking_transactions WHERE transaction_uid > "001233"
# May not work correctly with text comparison!
```

---

#### 2. **Amounts Stored with Wrong Precision (2 found)**
- `receipts.net_amount` = NUMERIC(None, None) ← NO PRECISION SPECIFIED!
- `receipts.revenue` = NUMERIC(None, None) ← NO PRECISION!

**Impact:**
- Can lose decimal places in calculations
- Inconsistent with other amounts (gross_amount = NUMERIC(14,2))
- Rounding errors accumulate

**Should be:**
```sql
receipts.net_amount = NUMERIC(14,2)  -- supports $99,999,999,999.99
receipts.revenue = NUMERIC(14,2)
```

---

#### 3. **Odometer Stored with scale=1 (loses cents precision)**
- `charters.odometer_start` = NUMERIC(10,1) ← Only 1 decimal place!
- `charters.odometer_end` = NUMERIC(10,1) ← Only 1 decimal place!
- `charters.total_kms` = NUMERIC(10,1) ← Only 1 decimal place!

**Problem:** Can store 123.4 but not 123.45 kilometers
```sql
INSERT INTO charters (odometer_start) VALUES (12345.67);
-- Stored as: 12345.7 (rounded down, data lost!)
```

**Should be:** NUMERIC(10,2)

---

### 🟡 MAJOR ISSUES

#### 4. **MASSIVE Column Redundancy (100+ tables)**

**Example - Receipts table has 6 amount columns:**
- `gross_amount` (total receipt)
- `gst_amount` (tax)
- `net_amount` (after tax)
- `fuel_amount` (fuel component)
- `owner_personal_amount` (personal expense component)
- `amount_usd` (currency conversion)

**Problem:** When calculating, which one do we use?
```python
# Is this correct?
total = r.gross_amount
# Or should it be:
total = r.net_amount
# Or:
total = r.gross_amount - r.gst_amount
```

**Payments table has 2 amount columns:**
- `amount` (one value)
- `payment_amount` (different value)

**Which is correct?**
```sql
SELECT * FROM payments WHERE amount = 100;
-- Returns 5 records

SELECT * FROM payments WHERE payment_amount = 100;
-- Returns 3 records (missing 2!)

-- Which columns should be used for reconciliation?
```

**Banking Transactions all have debit_amount AND credit_amount**
- Debit (money out): $50.00
- Credit (money in): NULL
- OR
- Debit: NULL
- Credit (money in): $50.00

**Should be:** ONE column `amount` with sign (+/-) or `transaction_type` (DEBIT/CREDIT)

---

#### 5. **Status/Type Columns Stored as TEXT (807 found)**
Should use ENUM or Foreign Keys:
- `charters.trip_status` = VARCHAR (values: "scheduled", "completed", "cancelled", etc.)
- `bookings.booking_status` = VARCHAR (values: "pending", "confirmed", "rejected")
- `receipts.validation_status` = TEXT

**Problem:** No type checking
```python
INSERT INTO charters (trip_status) VALUES ('complited');  # Typo! Accepted!
INSERT INTO charters (trip_status) VALUES ('COMPLETED');  # Different case!
INSERT INTO charters (trip_status) VALUES (NULL);         # Missing!
```

**Better with ENUM:**
```sql
CREATE TYPE trip_status_enum AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled');
ALTER TABLE charters ALTER COLUMN trip_status TYPE trip_status_enum;
-- Now only valid values allowed, case-insensitive
```

---

#### 6. **Duplicate Amount Columns in EVERY Table**
Receipts has 7 amount variations, charters has 7 price variations:
- `retainer_amount`
- `airport_pickup_price`
- `airport_dropoff_price`
- `default_hourly_price`
- `driver_gratuity_amount`
- `total_amount_due`
- `paid_amount`

**Is this correct?**
```sql
SELECT 
    COALESCE(airport_pickup_price, default_hourly_price) as base_price,
    driver_gratuity_amount,
    total_amount_due
FROM charters
WHERE charter_id = 12345;

-- What if all three are populated? Which one is authoritative?
```

---

### 🟢 GOOD NEWS

✅ **Amounts mostly stored correctly as NUMERIC(12,2) or NUMERIC(14,2)**
✅ **Dates stored as DATE or TIMESTAMP (not TEXT)**
✅ **Most IDs stored as INTEGER/BIGINT (except 20 edge cases)**
✅ **Booleans stored as BOOLEAN (except legacy columns)**

---

## Data Type Problems Specific to Split Receipts

### Payment Method Storage Issue
```sql
SELECT DISTINCT payment_method FROM receipts;
-- Returns: cash, check, credit_card, debit_card, debit, CHEQUE, gift_card, ...
```

**Problem:** Inconsistent naming
- `cash` vs `Cash` (case sensitive!)
- `credit_card` vs `CREDIT_CARD`
- `debit_card` vs `debit`
- `check` vs `CHEQUE`

**Solution:** Should be ENUM
```sql
CREATE TYPE payment_method_enum AS ENUM (
    'cash',
    'check',
    'credit_card',
    'debit_card',
    'bank_transfer',
    'gift_card',
    'personal',
    'trade_of_services',
    'unknown'
);
```

### GL Code Storage Issue
```sql
SELECT DISTINCT gl_account_code FROM receipts WHERE gl_account_code IS NOT NULL;
-- Returns: '1000', '1010', '1020', '2010', '2100', '6500', '6900', NULL
```

**Problem:** Stored as TEXT, should be linked to GL master table
```sql
-- Current (broken):
receipts.gl_account_code = '6900'  -- just text, no validation

-- Better:
ALTER TABLE receipts ADD CONSTRAINT fk_gl_code
FOREIGN KEY (gl_account_code) REFERENCES gl_code_master(gl_code);
```

---

## Recommended Fixes (Priority Order)

### Phase 1: Immediate (Affects Splits)
1. [ ] `receipts.net_amount` → ADD PRECISION NUMERIC(14,2)
2. [ ] `receipts.revenue` → ADD PRECISION NUMERIC(14,2)
3. [ ] Create `payment_method_enum` and enforce on receipts/payments
4. [ ] Create `gl_code_master` table and add FK constraint

### Phase 2: Short-term (Data Integrity)
1. [ ] Convert `banking_transactions.transaction_uid` from VARCHAR to BIGINT
2. [ ] Convert `charter_payments.charter_id` from VARCHAR to INTEGER
3. [ ] Fix odometer columns: NUMERIC(10,1) → NUMERIC(10,2)
4. [ ] Create `status_enum` types for common statuses

### Phase 3: Long-term (Cleanup)
1. [ ] Consolidate amount columns (use calculated views instead)
2. [ ] Consolidate debit_amount + credit_amount into signed amounts
3. [ ] Rename duplicate columns (amount vs payment_amount - pick ONE)
4. [ ] Document which amount column is "source of truth" for each entity

---

## Files Generated
- `audit_data_types.py` - Script to regenerate this audit anytime

## Conclusion

**Data types are 90% correct but have critical edge cases:**
- A few IDs stored as TEXT
- A couple amount fields with no precision
- 807 status columns should use ENUM instead of TEXT
- Split receipt system will work but could be more robust

**For Split Receipts specifically:**
- `payment_method` should be ENUM (not hardcoded list)
- `gl_account_code` should reference master table (not free text)
- These are working now but fragile
