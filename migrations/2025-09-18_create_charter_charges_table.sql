-- Migration: Create charter_charges table for Arrow Limousine

CREATE TABLE IF NOT EXISTS charter_charges (
    charge_id SERIAL PRIMARY KEY,
    charter_id INTEGER REFERENCES charters(charter_id) ON DELETE CASCADE,
    charge_type VARCHAR(50) NOT NULL, -- e.g. 'gst', 'gratuity', 'extra', 'invoice', etc.
    amount NUMERIC(12,2) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookup by charter
CREATE INDEX IF NOT EXISTS idx_charter_charges_charter_id ON charter_charges(charter_id);
