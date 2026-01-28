-- Migration: Add vendor suffix columns to card_transaction_staging
-- Date: 2025-09-30
-- Purpose: Store extracted vendor tail (possibly truncated) and a truncation flag for later normalization.

BEGIN;

ALTER TABLE card_transaction_staging
    ADD COLUMN IF NOT EXISTS raw_vendor_suffix VARCHAR(200),
    ADD COLUMN IF NOT EXISTS vendor_truncated BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_card_staging_vendor_suffix ON card_transaction_staging(raw_vendor_suffix);

COMMIT;
