-- Add vendor account enhancements
-- Run: psql -h localhost -U postgres -d almsdata -f migrations/2025-12-27_vendor_account_enhancements.sql

-- Add vendor_account_id FK to receipts for direct linkage
ALTER TABLE receipts 
ADD COLUMN IF NOT EXISTS vendor_account_id BIGINT REFERENCES vendor_accounts(account_id) ON DELETE SET NULL;

-- Add payment terms
ALTER TABLE vendor_accounts 
ADD COLUMN IF NOT EXISTS payment_terms VARCHAR(20);

-- Add contact email
ALTER TABLE vendor_accounts 
ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);

-- Add account notes
ALTER TABLE vendor_accounts 
ADD COLUMN IF NOT EXISTS notes TEXT;

-- Add account status
ALTER TABLE vendor_accounts 
ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';

ALTER TABLE vendor_accounts
ADD CONSTRAINT status_ck CHECK (status IN ('active', 'inactive', 'archived'));

-- Create index on vendor_account_id
CREATE INDEX IF NOT EXISTS idx_receipts_vendor_account_id ON receipts(vendor_account_id);

-- Backfill vendor_account_id based on canonical_vendor
UPDATE receipts r
SET vendor_account_id = va.account_id
FROM vendor_accounts va
WHERE r.canonical_vendor IS NOT NULL 
  AND UPPER(r.canonical_vendor) = UPPER(va.canonical_vendor)
  AND r.vendor_account_id IS NULL;

COMMENT ON COLUMN receipts.vendor_account_id IS 'Direct link to vendor account for payables tracking';
COMMENT ON COLUMN vendor_accounts.payment_terms IS 'Payment terms (NET30, NET60, etc.)';
COMMENT ON COLUMN vendor_accounts.contact_email IS 'Email for sending statement requests';
