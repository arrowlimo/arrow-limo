-- STEP 2B: Driver Inspection, HOS, Receipts, & Pay - database changes
-- Date: 2026-01-22
-- Note: reserve_number is the business key; avoid relying on charter_id for business logic.

BEGIN;

-- 1) Charters: reserve_number business key (if not present), then NRD, out-of-town, extra time, breakdown, Red Deer bylaw fields
ALTER TABLE charters
  ADD COLUMN IF NOT EXISTS reserve_number VARCHAR(50) UNIQUE,
  ADD COLUMN IF NOT EXISTS nrd_received BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS nrd_received_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS nrd_amount DECIMAL(12,2),
  ADD COLUMN IF NOT EXISTS nrd_method VARCHAR(20), -- cash/check/card/bank_transfer
  ADD COLUMN IF NOT EXISTS is_out_of_town BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS leave_red_deer_at TIME,
  ADD COLUMN IF NOT EXISTS return_to_red_deer_by TIME,
  ADD COLUMN IF NOT EXISTS red_deer_bylaw_exempt BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS extra_time_started TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS actual_return_to_red_deer_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS extra_time_hours DECIMAL(5,2),
  ADD COLUMN IF NOT EXISTS extra_time_charges DECIMAL(12,2),
  ADD COLUMN IF NOT EXISTS vehicle_broke_down BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS vehicle_breakdown_time TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS replacement_vehicle_arrived_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS transport_arrangement_made VARCHAR(255),
  ADD COLUMN IF NOT EXISTS poor_service_reimbursement DECIMAL(12,2),
  ADD COLUMN IF NOT EXISTS poor_service_reason VARCHAR(50), -- breakdown, late_pickup, wrong_vehicle, no_show, etc.
  ADD COLUMN IF NOT EXISTS poor_service_notes TEXT,
  ADD COLUMN IF NOT EXISTS vehicle_start_odometer NUMERIC,
  ADD COLUMN IF NOT EXISTS vehicle_end_odometer NUMERIC,
  ADD COLUMN IF NOT EXISTS vehicle_total_distance NUMERIC,
  ADD COLUMN IF NOT EXISTS fuel_added_liters DECIMAL(8,2),
  ADD COLUMN IF NOT EXISTS float_received DECIMAL(12,2),
  ADD COLUMN IF NOT EXISTS float_reimbursement_needed DECIMAL(12,2);

-- 2) Employees: pay rate, gratuity, qualifications
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS hourly_pay_rate DECIMAL(8,2),
  ADD COLUMN IF NOT EXISTS gratuity_eligible BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS gratuity_percentage INT DEFAULT 100,
  ADD COLUMN IF NOT EXISTS cvip_certified BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS cvip_expiry DATE,
  ADD COLUMN IF NOT EXISTS red_deer_compliant BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS red_deer_required BOOLEAN DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS license_class VARCHAR(10),
  ADD COLUMN IF NOT EXISTS medical_fitness_expiry DATE;

-- 3) Vehicles: tier, maintenance, Red Deer compliance
ALTER TABLE vehicles
  ADD COLUMN IF NOT EXISTS tier_id INT, -- FK to vehicle_capacity_tiers (optional)
  ADD COLUMN IF NOT EXISTS maintenance_start_date DATE,
  ADD COLUMN IF NOT EXISTS maintenance_end_date DATE,
  ADD COLUMN IF NOT EXISTS is_in_maintenance BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS red_deer_compliant BOOLEAN DEFAULT FALSE;

-- 4) Vehicle capacity tiers (optional, for tier-based fallback)
CREATE TABLE IF NOT EXISTS vehicle_capacity_tiers (
  tier_id SERIAL PRIMARY KEY,
  tier_name VARCHAR(50) UNIQUE NOT NULL, -- e.g., "4-Passenger", "6-7 Passenger"
  min_capacity INT,
  max_capacity INT,
  tier_group INT, -- 1-5 for fallback grouping
  display_order INT
);

-- Optional FK
-- ALTER TABLE vehicles ADD CONSTRAINT fk_vehicles_tier FOREIGN KEY (tier_id) REFERENCES vehicle_capacity_tiers(tier_id);

-- 5) Charter routing times (dual entry: dispatcher + driver)
CREATE TABLE IF NOT EXISTS charters_routing_times (
  routing_time_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  route_sequence INT,
  leg_description TEXT,
  dispatcher_expected_time TIME,
  dispatcher_notes TEXT,
  driver_actual_time TIME,
  driver_notes VARCHAR(255),
  leg_status VARCHAR(20), -- on_time, late, early, issue
  recorded_by VARCHAR(100),
  recorded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_routing_times_reserve ON charters_routing_times(reserve_number);

-- 6) HOS log
CREATE TABLE IF NOT EXISTS hos_log (
  hos_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  employee_id INT REFERENCES employees(employee_id),
  hos_date DATE,
  on_duty_start TIMESTAMPTZ,
  break_start TIMESTAMPTZ,
  break_duration INT, -- minutes
  break_end TIMESTAMPTZ,
  off_duty_at TIMESTAMPTZ,
  on_duty_hours DECIMAL(5,2),
  off_duty_hours DECIMAL(5,2),
  exemption_claimed BOOLEAN DEFAULT FALSE,
  exemption_type VARCHAR(100), -- "160-hour-tour", etc.
  hos_status VARCHAR(20), -- compliant, warning, violation
  logbook_required BOOLEAN DEFAULT FALSE,
  logbook_submitted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100),
  locked_at TIMESTAMPTZ,
  locked_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_hos_log_reserve ON hos_log(reserve_number);
CREATE INDEX IF NOT EXISTS idx_hos_log_employee_date ON hos_log(employee_id, hos_date DESC);

-- 7) HOS 14-day summary (cached for performance)
CREATE TABLE IF NOT EXISTS hos_14day_summary (
  summary_id SERIAL PRIMARY KEY,
  employee_id INT REFERENCES employees(employee_id),
  start_date DATE,
  end_date DATE,
  total_on_duty DECIMAL(6,2), -- hours
  total_off_duty DECIMAL(6,2),
  compliant BOOLEAN,
  violations TEXT, -- JSON array of violation descriptions
  generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hos_14day_employee ON hos_14day_summary(employee_id, end_date DESC);

-- 8) Charter receipts (fuel, tolls, expenses)
CREATE TABLE IF NOT EXISTS charter_receipts (
  receipt_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  vehicle_id INT REFERENCES vehicles(vehicle_id),
  receipt_date DATE,
  vendor VARCHAR(255),
  category VARCHAR(50), -- fuel, toll, parking, meals, etc.
  amount DECIMAL(12,2),
  payment_method VARCHAR(20), -- cash, card, direct
  receipt_image_url VARCHAR(500), -- file upload
  banking_transaction_id INT, -- NULL if cash; refs banking_transactions if card
  status VARCHAR(20), -- pending, reimbursed, advance, reconciled
  notes TEXT,
  created_by VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  matched_by VARCHAR(100),
  matched_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_charter_receipts_reserve ON charter_receipts(reserve_number);
CREATE INDEX IF NOT EXISTS idx_charter_receipts_vehicle ON charter_receipts(vehicle_id);

-- 9) Beverage orders
CREATE TABLE IF NOT EXISTS charter_beverage_orders (
  beverage_order_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100),
  purchase_receipt_url VARCHAR(500), -- scanned receipt for police
  receipt_attached BOOLEAN DEFAULT FALSE,
  total_amount DECIMAL(12,2),
  gst_amount DECIMAL(12,2),
  deposit_amount DECIMAL(12,2),
  grand_total DECIMAL(12,2),
  driver_verified BOOLEAN DEFAULT FALSE,
  driver_verified_at TIMESTAMPTZ,
  driver_verified_by VARCHAR(100),
  discrepancies TEXT
);

CREATE INDEX IF NOT EXISTS idx_beverage_orders_reserve ON charter_beverage_orders(reserve_number);

-- 10) Beverage line items
CREATE TABLE IF NOT EXISTS charter_beverage_items (
  beverage_item_id SERIAL PRIMARY KEY,
  beverage_order_id INT REFERENCES charter_beverage_orders(beverage_order_id) ON DELETE CASCADE,
  item_type VARCHAR(255), -- "Beer - Molson Canadian (24-pack)"
  quantity INT,
  unit_price DECIMAL(12,2),
  gst_per_line DECIMAL(12,2),
  deposit_per_line DECIMAL(12,2),
  line_total DECIMAL(12,2),
  driver_count INT, -- actual count verified by driver
  stocked BOOLEAN DEFAULT FALSE, -- checkbox marked
  notes TEXT
);

-- 11) Driver pay tracking (per charter)
CREATE TABLE IF NOT EXISTS charter_driver_pay (
  driver_pay_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  employee_id INT REFERENCES employees(employee_id),
  suggested_hours DECIMAL(5,2), -- auto-calculated from HOS
  actual_payable_hours DECIMAL(5,2), -- dispatcher-adjusted
  suggested_gratuity DECIMAL(12,2), -- auto-calculated from invoice
  actual_gratuity_owed DECIMAL(12,2), -- dispatcher-adjusted
  pay_rate DECIMAL(8,2), -- from employee record at time of charter
  total_driver_pay DECIMAL(12,2), -- (actual_hours × pay_rate) + actual_gratuity
  effective_hourly DECIMAL(8,2), -- total_driver_pay ÷ actual_payable_hours (auto-calc via trigger)
  float_received DECIMAL(12,2), -- cash advance for trip expenses
  total_receipts_submitted DECIMAL(12,2), -- SUM of all receipts for this charter
  float_balance DECIMAL(12,2), -- float_received - total_receipts (+ = owe company, - = owe driver)
  net_amount_owed DECIMAL(12,2), -- total_driver_pay - float_balance (final settlement)
  pay_status VARCHAR(20), -- pending, approved, paid, held
  pay_notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100),
  approved_by VARCHAR(100),
  approved_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  payroll_batch_id INT -- link to payroll processing
);

CREATE INDEX IF NOT EXISTS idx_charter_driver_pay_reserve ON charter_driver_pay(reserve_number);
CREATE INDEX IF NOT EXISTS idx_charter_driver_pay_employee ON charter_driver_pay(employee_id, pay_status);

COMMIT;
