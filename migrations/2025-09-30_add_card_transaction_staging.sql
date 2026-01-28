-- Migration: Card transaction staging table
-- Date: 2025-09-30
-- Purpose: Temporary holding area for raw merged monthly credit/debit card CSV files from CIBC (3 accounts consolidated).

BEGIN;

CREATE TABLE IF NOT EXISTS card_transaction_staging (
    staging_id SERIAL PRIMARY KEY,
    source_account_label VARCHAR(100),  -- Provided label: e.g. 'Canadian Tire MC', 'RBC Visa', etc.
    source_filename VARCHAR(255),       -- Origin CSV for traceability
    statement_month DATE,               -- Normalized to first day of month (yyyy-mm-01)
    post_date DATE,
    trans_date DATE,
    raw_description TEXT,
    amount DECIMAL(12,2),               -- Positive for charges, negative for credits/refunds OR keep sign as in file
    currency_code CHAR(3) DEFAULT 'CAD',
    card_last4 VARCHAR(4),              -- Extracted from file or mapped externally
    category_hint TEXT,                 -- If card export has category
    merchant_extracted VARCHAR(200),
    hash_fingerprint VARCHAR(64),       -- Deterministic hash to prevent duplicate loads
    load_batch_id VARCHAR(64),
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    UNIQUE(hash_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_card_staging_dates ON card_transaction_staging(post_date, trans_date);
CREATE INDEX IF NOT EXISTS idx_card_staging_last4 ON card_transaction_staging(card_last4);
CREATE INDEX IF NOT EXISTS idx_card_staging_account_label ON card_transaction_staging(source_account_label);

COMMIT;
