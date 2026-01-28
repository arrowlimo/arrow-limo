-- Create payments table for Arrow Limousine

CREATE TABLE IF NOT EXISTS payments (
    payment_id SERIAL PRIMARY KEY,
    charter_id INTEGER REFERENCES charters(charter_id) ON DELETE SET NULL,
    amount NUMERIC(12,2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_method VARCHAR(50) DEFAULT 'credit_card',
    payment_key VARCHAR(255), -- external id (e.g., Square Payment ID)
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_payments_charter_id ON payments(charter_id);
-- Use non-unique partial index to avoid failures if historical data contains duplicate keys
CREATE INDEX IF NOT EXISTS idx_payments_payment_key ON payments(payment_key) WHERE payment_key IS NOT NULL;
