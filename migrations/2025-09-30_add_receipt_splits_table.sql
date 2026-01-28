-- Migration: Optional normalized receipt_splits table
-- Date: 2025-09-30
-- Purpose: Provide a structured place to store parsed split allocations derived from SPLIT/<gross> duplicated receipt rows.

BEGIN;

CREATE TABLE IF NOT EXISTS receipt_splits (
    split_id SERIAL PRIMARY KEY,
    receipt_group_key VARCHAR(100) NOT NULL, -- hash or derived grouping id across duplicated rows
    receipt_id INTEGER REFERENCES receipts(receipt_id) ON DELETE CASCADE,
    original_receipt_date DATE,
    vendor_name VARCHAR(255),
    gross_amount DECIMAL(12,2) NOT NULL,      -- Declared full amount (SPLIT/<gross>)
    component_amount DECIMAL(12,2) NOT NULL,  -- Portion represented by this line
    component_type VARCHAR(50),               -- fuel / food / cash / card / other
    source_row_note TEXT,                     -- Original note text for traceability
    parsed_ok BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(receipt_id, component_type)
);

CREATE INDEX IF NOT EXISTS idx_receipt_splits_group ON receipt_splits(receipt_group_key);

COMMIT;
