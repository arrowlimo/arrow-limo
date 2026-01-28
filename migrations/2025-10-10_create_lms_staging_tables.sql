-- Staging tables for LMS Access sync
CREATE TABLE IF NOT EXISTS lms_staging_reserve (
  reserve_no TEXT PRIMARY KEY,
  last_updated TIMESTAMPTZ,
  raw_data JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lms_staging_payment (
  payment_id INTEGER PRIMARY KEY,
  reserve_no TEXT,
  last_updated TIMESTAMPTZ,
  raw_data JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lms_staging_customer (
  customer_id INTEGER PRIMARY KEY,
  last_updated TIMESTAMPTZ,
  raw_data JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS lms_staging_vehicles (
  vehicle_code TEXT PRIMARY KEY,
  vin TEXT,
  last_updated TIMESTAMPTZ,
  raw_data JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Helpful indexes (no-ops on small tables but fine to add)
CREATE INDEX IF NOT EXISTS idx_lms_staging_reserve_last_updated ON lms_staging_reserve(last_updated);
CREATE INDEX IF NOT EXISTS idx_lms_staging_payment_last_updated ON lms_staging_payment(last_updated);
CREATE INDEX IF NOT EXISTS idx_lms_staging_customer_last_updated ON lms_staging_customer(last_updated);
CREATE INDEX IF NOT EXISTS idx_lms_staging_vehicles_last_updated ON lms_staging_vehicles(last_updated);
