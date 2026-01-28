-- Migration: create email_payment_links table (idempotent)
CREATE TABLE IF NOT EXISTS email_payment_links (
  id SERIAL PRIMARY KEY,
  payment_id INTEGER REFERENCES payments(payment_id) ON DELETE CASCADE,
  reserve_number VARCHAR(10),
  email_received TIMESTAMP,
  email_subject TEXT,
  email_type VARCHAR(20), -- etransfer | square | banking
  amount NUMERIC(12,2),
  source_hash CHAR(64) UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Helpful index for lookup by reserve/amount/date
CREATE INDEX IF NOT EXISTS idx_email_payment_links_reserve_amount_date
  ON email_payment_links(reserve_number, amount, email_received);