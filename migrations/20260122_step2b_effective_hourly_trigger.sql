-- Trigger: Auto-calculate effective_hourly on charter_driver_pay
-- Date: 2026-01-22
-- Formula: effective_hourly = total_driver_pay ÷ actual_payable_hours (rounded to 2 decimal places)

BEGIN;

CREATE OR REPLACE FUNCTION calc_effective_hourly()
RETURNS TRIGGER AS $$
BEGIN
  -- Only calculate if actual_payable_hours > 0 to avoid division by zero
  IF NEW.actual_payable_hours IS NOT NULL AND NEW.actual_payable_hours > 0 THEN
    NEW.effective_hourly := ROUND(NEW.total_driver_pay / NEW.actual_payable_hours, 2);
  ELSE
    NEW.effective_hourly := NULL;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on charter_driver_pay (before INSERT or UPDATE)
DROP TRIGGER IF EXISTS trg_calc_effective_hourly ON charter_driver_pay;
CREATE TRIGGER trg_calc_effective_hourly
  BEFORE INSERT OR UPDATE ON charter_driver_pay
  FOR EACH ROW
  EXECUTE FUNCTION calc_effective_hourly();

COMMIT;
