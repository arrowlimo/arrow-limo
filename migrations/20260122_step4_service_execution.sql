-- STEP 4: Service Execution (Charter Day) - database changes
-- Date: 2026-01-22
-- Note: reserve_number is the business key; avoid charter_id for business logic.

BEGIN;

-- 1) Charters: live status tracking, execution timestamps
ALTER TABLE charters
  ADD COLUMN IF NOT EXISTS status VARCHAR(50), -- In Progress, On Location, Passengers Loaded, En Route to Event, At Event, Return Journey, Completed, Cancelled
  ADD COLUMN IF NOT EXISTS on_duty_started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS on_location_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS passengers_loaded_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS en_route_to_event_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS arrived_at_event_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS return_journey_started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS off_duty_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS current_status_updated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS current_status_updated_by VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_charters_status ON charters(status);

-- 2) Charter incidents (breakdown, late, complaint, medical, accident)
CREATE TABLE IF NOT EXISTS charter_incidents (
  incident_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  incident_type VARCHAR(50), -- breakdown, late, wrong_vehicle, complaint, medical, accident, other
  incident_severity VARCHAR(20), -- minor, major
  occurred_at TIMESTAMPTZ,
  description TEXT,
  poor_service_reimbursement DECIMAL(12,2), -- auto-discount or credit
  gratuity_impact BOOLEAN DEFAULT FALSE, -- TRUE if gratuity forfeited
  requires_manager_review BOOLEAN DEFAULT FALSE, -- TRUE for major incidents
  manager_reviewed_by VARCHAR(100),
  manager_reviewed_at TIMESTAMPTZ,
  resolution_notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_incidents_reserve ON charter_incidents(reserve_number);
CREATE INDEX IF NOT EXISTS idx_incidents_type_severity ON charter_incidents(incident_type, incident_severity);
CREATE INDEX IF NOT EXISTS idx_incidents_manager_review ON charter_incidents(requires_manager_review, manager_reviewed_at);

-- 3) Customer communication log (proactive updates, delay notifications)
CREATE TABLE IF NOT EXISTS customer_comms_log (
  comm_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  comm_type VARCHAR(20), -- phone, sms, email
  sent_at TIMESTAMPTZ,
  sent_by VARCHAR(100), -- dispatcher or system
  subject VARCHAR(255),
  message_summary TEXT,
  delivery_status VARCHAR(20), -- sent, delivered, failed
  customer_response TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_comms_reserve ON customer_comms_log(reserve_number);
CREATE INDEX IF NOT EXISTS idx_customer_comms_sent_at ON customer_comms_log(sent_at DESC);

COMMIT;
