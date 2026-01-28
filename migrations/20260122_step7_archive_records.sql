-- STEP 7: Archive & Records Management - database changes
-- Date: 2026-01-22
-- Note: reserve_number is the business key; 7-year retention minimum.

-- Ensure invoices table exists before creating views
CREATE TABLE IF NOT EXISTS invoices (
  invoice_id SERIAL PRIMARY KEY,
  reserve_number VARCHAR(50) NOT NULL UNIQUE,
  invoice_total DECIMAL(12,2),
  total_payments DECIMAL(12,2),
  balance_due DECIMAL(12,2),
  invoice_status VARCHAR(20),
  due_date DATE
);

BEGIN;

-- 1) Charters: archive tracking
ALTER TABLE charters
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS archived_by VARCHAR(100),
  ADD COLUMN IF NOT EXISTS archive_notes TEXT;

CREATE INDEX IF NOT EXISTS idx_charters_archived_at ON charters(archived_at);
CREATE INDEX IF NOT EXISTS idx_charters_active_status ON charters(status) WHERE archived_at IS NULL;

-- 2) View: Revenue summary (monthly aggregation)
CREATE OR REPLACE VIEW v_revenue_summary AS
SELECT
  DATE_TRUNC('month', c.charter_date) AS month,
  COUNT(DISTINCT c.reserve_number) AS total_charters,
  SUM(i.invoice_total) AS total_invoiced,
  SUM(i.total_payments) AS total_paid,
  SUM(i.balance_due) AS total_outstanding
FROM charters c
LEFT JOIN invoices i ON c.reserve_number = i.reserve_number
WHERE c.status IS NULL OR c.status != 'Cancelled'
GROUP BY DATE_TRUNC('month', c.charter_date)
ORDER BY month DESC;

-- 3) View: Driver pay summary (by employee, by period)
CREATE OR REPLACE VIEW v_driver_pay_summary AS
SELECT
  e.employee_id,
  e.first_name,
  e.last_name,
  DATE_TRUNC('month', c.charter_date) AS pay_period,
  COUNT(DISTINCT c.reserve_number) AS total_charters,
  SUM(dp.actual_payable_hours) AS total_hours,
  SUM(dp.total_driver_pay) AS total_pay,
  AVG(dp.effective_hourly) AS avg_effective_hourly
FROM charter_driver_pay dp
JOIN employees e ON dp.employee_id = e.employee_id
JOIN charters c ON dp.reserve_number = c.reserve_number
WHERE dp.pay_status IN ('approved', 'paid')
GROUP BY e.employee_id, e.first_name, e.last_name, DATE_TRUNC('month', c.charter_date)
ORDER BY pay_period DESC, total_pay DESC;

-- 4) View: Vehicle utilization (by month)
CREATE OR REPLACE VIEW v_vehicle_utilization AS
SELECT
  v.vehicle_id,
  v.year,
  v.make,
  v.model,
  DATE_TRUNC('month', c.charter_date) AS month,
  COUNT(DISTINCT c.reserve_number) AS total_charters,
  SUM(c.vehicle_total_distance) AS total_distance,
  AVG(c.vehicle_total_distance) AS avg_distance_per_charter
FROM charters c
JOIN vehicles v ON c.vehicle_id = v.vehicle_id
WHERE c.status = 'Completed'
GROUP BY v.vehicle_id, v.year, v.make, v.model, DATE_TRUNC('month', c.charter_date)
ORDER BY month DESC, total_charters DESC;

-- 5) View: Incident trends (by type, by month)
CREATE OR REPLACE VIEW v_incident_trends AS
SELECT
  DATE_TRUNC('month', occurred_at) AS month,
  incident_type,
  incident_severity,
  COUNT(*) AS total_incidents,
  SUM(CASE WHEN gratuity_impact THEN 1 ELSE 0 END) AS gratuity_forfeitures,
  SUM(poor_service_reimbursement) AS total_reimbursements
FROM charter_incidents
GROUP BY DATE_TRUNC('month', occurred_at), incident_type, incident_severity
ORDER BY month DESC, total_incidents DESC;

-- 6) View: HOS compliance summary (by employee, by period)
CREATE OR REPLACE VIEW v_hos_compliance_summary AS
SELECT
  e.employee_id,
  e.first_name,
  e.last_name,
  DATE_TRUNC('month', hl.hos_date) AS compliance_period,
  COUNT(*) AS total_shifts,
  SUM(CASE WHEN hl.hos_status = 'compliant' THEN 1 ELSE 0 END) AS compliant_shifts,
  SUM(CASE WHEN hl.hos_status = 'warning' THEN 1 ELSE 0 END) AS warning_shifts,
  SUM(CASE WHEN hl.hos_status = 'violation' THEN 1 ELSE 0 END) AS violation_shifts,
  SUM(CASE WHEN hl.logbook_required THEN 1 ELSE 0 END) AS logbook_required_shifts
FROM hos_log hl
JOIN employees e ON hl.employee_id = e.employee_id
GROUP BY e.employee_id, e.first_name, e.last_name, DATE_TRUNC('month', hl.hos_date)
ORDER BY compliance_period DESC, violation_shifts DESC;

-- 7) View: Outstanding receivables (overdue invoices)
CREATE OR REPLACE VIEW v_outstanding_receivables AS
SELECT
  i.reserve_number,
  c.charter_date,
  COALESCE(c.client_display_name, 'Unknown Customer') AS customer_name,
  i.invoice_number,
  i.invoice_date,
  i.due_date,
  CURRENT_DATE - i.due_date AS days_overdue,
  i.invoice_total,
  i.total_payments,
  i.balance_due,
  i.invoice_status
FROM invoices i
JOIN charters c ON i.reserve_number = c.reserve_number
WHERE i.balance_due > 0 AND i.invoice_status != 'credited'
ORDER BY i.due_date ASC;

COMMIT;
