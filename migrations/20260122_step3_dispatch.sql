-- STEP 3: Dispatch & Service Day - database changes (draft)
-- Date: 2026-01-22
-- Note: reserve_number is the business key; avoid relying on charter_id for business logic.

BEGIN;

-- 1) Charters: driver acknowledgment + dispatch audit fields
ALTER TABLE charters
  ADD COLUMN IF NOT EXISTS driver_acknowledged_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS driver_ack_method VARCHAR(20), -- sms/email/phone/app
  ADD COLUMN IF NOT EXISTS driver_ack_notes TEXT,
  ADD COLUMN IF NOT EXISTS dispatch_last_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS dispatch_updated_by VARCHAR(100);

-- Useful indexes
CREATE INDEX IF NOT EXISTS idx_charters_driver_ack_reserve
  ON charters (reserve_number, driver_acknowledged_at DESC);
CREATE INDEX IF NOT EXISTS idx_charters_dispatch_updated
  ON charters (dispatch_last_updated_at DESC);

-- 2) Dispatch events audit (business key = reserve_number)
CREATE TABLE IF NOT EXISTS dispatch_events (
  dispatch_event_id SERIAL PRIMARY KEY,
  reserve_number VARCHAR(50) NOT NULL,
  event_type VARCHAR(50) NOT NULL, -- time_change, vehicle_swap, driver_swap, routing_change, beverage_change, payment_update
  old_value JSONB,
  new_value JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_dispatch_events_reserve
  ON dispatch_events (reserve_number);
CREATE INDEX IF NOT EXISTS idx_dispatch_events_type
  ON dispatch_events (event_type);

-- Optional FK (enable if charters.reserve_number is present and unique)
-- ALTER TABLE dispatch_events
--   ADD CONSTRAINT fk_dispatch_events_reserve
--   FOREIGN KEY (reserve_number) REFERENCES charters(reserve_number);

-- 3) Driver communications log
CREATE TABLE IF NOT EXISTS driver_comms_log (
  comm_id SERIAL PRIMARY KEY,
  reserve_number VARCHAR(50),
  employee_id INT REFERENCES employees(employee_id),
  method VARCHAR(20), -- sms/email/phone/app
  sent_at TIMESTAMPTZ DEFAULT NOW(),
  acknowledged_at TIMESTAMPTZ,
  message_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_driver_comms_reserve
  ON driver_comms_log (reserve_number);
CREATE INDEX IF NOT EXISTS idx_driver_comms_ack
  ON driver_comms_log (acknowledged_at);

-- Optional FK to charters on reserve_number (enable if appropriate)
-- ALTER TABLE driver_comms_log
--   ADD CONSTRAINT fk_driver_comms_reserve
--   FOREIGN KEY (reserve_number) REFERENCES charters(reserve_number);

-- 4) Effective hourly auto-calc trigger for charter_driver_pay
CREATE OR REPLACE FUNCTION calc_effective_hourly() RETURNS trigger AS $$
BEGIN
  IF NEW.actual_payable_hours IS NOT NULL AND NEW.actual_payable_hours > 0 THEN
    NEW.effective_hourly := ROUND(NEW.total_driver_pay / NEW.actual_payable_hours, 2);
  ELSE
    NEW.effective_hourly := NULL;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS charter_driver_pay_calc_eff ON charter_driver_pay;
CREATE TRIGGER charter_driver_pay_calc_eff
BEFORE INSERT OR UPDATE ON charter_driver_pay
FOR EACH ROW
EXECUTE FUNCTION calc_effective_hourly();

COMMIT;
