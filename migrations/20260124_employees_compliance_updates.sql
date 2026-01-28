-- Drop redundant driver_code; add compliance/licensing fields
-- Handle dependent view first
DROP VIEW IF EXISTS todays_schedule;

ALTER TABLE employees
    DROP CONSTRAINT IF EXISTS employees_driver_code_key,
    DROP COLUMN IF EXISTS driver_code,
    ADD COLUMN IF NOT EXISTS vulnerable_sector_check_date date,
    ADD COLUMN IF NOT EXISTS drivers_abstract_date date,
    ADD COLUMN IF NOT EXISTS proserve_number character varying,
    ADD COLUMN IF NOT EXISTS proserve_expiry date,
    ADD COLUMN IF NOT EXISTS bylaw_permit_renewal_fee numeric(12,2) DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS driver_license_class character varying,
    ADD COLUMN IF NOT EXISTS driver_license_restrictions text;

-- Recreate todays_schedule view using employee_number in place of driver_code
CREATE VIEW todays_schedule AS
SELECT
    c.charter_id,
    c.reserve_number,
    c.assigned_driver_id,
    e.full_name AS driver_name,
    e.employee_number AS driver_code,
    c.trip_status,
    c.client_id,
    cl.company_name AS client_name,
    c.pickup_time,
    c.pickup_address,
    c.dropoff_address,
    c.vehicle AS vehicle_description,
    c.driver AS driver_description,
    c.actual_start_time,
    c.actual_end_time,
    c.driver_notes,
    c.client_notes,
    c.booking_notes,
    c.special_requirements,
    c.retainer_received,
    c.retainer_amount,
    c.total_amount_due,
    c.payment_instructions,
    c.beverage_service_required,
    c.accessibility_required,
    c.status,
    c.charter_date
FROM charters c
LEFT JOIN employees e ON c.assigned_driver_id = e.employee_id
LEFT JOIN clients cl ON c.client_id = cl.client_id
WHERE c.charter_date = CURRENT_DATE AND c.cancelled = false
ORDER BY c.pickup_time;
