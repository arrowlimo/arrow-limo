-- STEP 5: Trip Completion & Closeout - database changes
-- Date: 2026-01-22
-- Note: reserve_number is the business key; avoid charter_id for business logic.

BEGIN;

-- 1) Charters: completion & validation fields
ALTER TABLE charters
  ADD COLUMN IF NOT EXISTS completion_timestamp TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS completed_by VARCHAR(100),
  ADD COLUMN IF NOT EXISTS completion_validated BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS completion_blockers TEXT, -- JSON array of unresolved issues
  ADD COLUMN IF NOT EXISTS driver_pay_approved BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS driver_pay_approved_by VARCHAR(100),
  ADD COLUMN IF NOT EXISTS driver_pay_approved_at TIMESTAMPTZ;

-- 2) Customer feedback (optional, post-trip)
CREATE TABLE IF NOT EXISTS customer_feedback (
  feedback_id SERIAL PRIMARY KEY,
  charter_id INT REFERENCES charters(charter_id),
  reserve_number VARCHAR(50), -- business key
  feedback_type VARCHAR(20), -- positive, neutral, complaint
  feedback_source VARCHAR(20), -- email, phone, survey, unsolicited
  feedback_text TEXT,
  rating INT, -- 1-5 or NULL
  incident_id INT, -- FK to charter_incidents if related
  requires_follow_up BOOLEAN DEFAULT FALSE,
  follow_up_completed BOOLEAN DEFAULT FALSE,
  follow_up_notes TEXT,
  submitted_at TIMESTAMPTZ DEFAULT NOW(),
  submitted_by VARCHAR(100), -- dispatcher who logged it
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_feedback_reserve ON customer_feedback(reserve_number);
CREATE INDEX IF NOT EXISTS idx_customer_feedback_type ON customer_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_customer_feedback_follow_up ON customer_feedback(requires_follow_up, follow_up_completed);

COMMIT;
