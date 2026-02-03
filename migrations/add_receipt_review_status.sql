-- Add comprehensive receipt review status tracking
-- This allows us to distinguish between:
--   verified: Receipt physically reviewed and data confirmed correct
--   missing: Receipt is missing/lost (create entry in missing_receipt_tracking)
--   unreadable: Receipt exists but is illegible/damaged
--   data-error: Receipt data doesn't match transaction (needs correction)

-- Add receipt_review_status column
ALTER TABLE receipts
ADD COLUMN IF NOT EXISTS receipt_review_status VARCHAR(20) DEFAULT NULL;

-- Add receipt_review_notes column for details
ALTER TABLE receipts
ADD COLUMN IF NOT EXISTS receipt_review_notes TEXT DEFAULT NULL;

-- Add receipt_reviewed_at timestamp
ALTER TABLE receipts
ADD COLUMN IF NOT EXISTS receipt_reviewed_at TIMESTAMP DEFAULT NULL;

-- Add receipt_reviewed_by user tracking
ALTER TABLE receipts
ADD COLUMN IF NOT EXISTS receipt_reviewed_by VARCHAR(100) DEFAULT NULL;

-- Create index for filtering by review status
CREATE INDEX IF NOT EXISTS idx_receipts_review_status 
ON receipts(receipt_review_status, receipt_reviewed_at);

-- Add check constraint for valid statuses
ALTER TABLE receipts
ADD CONSTRAINT chk_receipt_review_status
CHECK (receipt_review_status IN (NULL, 'verified', 'missing', 'unreadable', 'data-error'));

-- Add comments for documentation
COMMENT ON COLUMN receipts.receipt_review_status IS 
'Manual review status: verified (confirmed correct), missing (lost/unavailable), unreadable (damaged/illegible), data-error (requires correction)';

COMMENT ON COLUMN receipts.receipt_review_notes IS 
'Notes from manual review: reason for missing, description of damage, correction needed, etc.';

COMMENT ON COLUMN receipts.receipt_reviewed_at IS 
'Timestamp when receipt was manually reviewed';

COMMENT ON COLUMN receipts.receipt_reviewed_by IS 
'Username/identifier of person who reviewed the receipt';

-- Create view for receipt review summary
CREATE OR REPLACE VIEW receipt_review_summary AS
SELECT 
    COUNT(*) as total_receipts,
    COUNT(CASE WHEN receipt_review_status = 'verified' THEN 1 END) as verified_count,
    COUNT(CASE WHEN receipt_review_status = 'missing' THEN 1 END) as missing_count,
    COUNT(CASE WHEN receipt_review_status = 'unreadable' THEN 1 END) as unreadable_count,
    COUNT(CASE WHEN receipt_review_status = 'data-error' THEN 1 END) as data_error_count,
    COUNT(CASE WHEN receipt_review_status IS NULL THEN 1 END) as not_reviewed_count,
    ROUND(100.0 * COUNT(CASE WHEN receipt_review_status = 'verified' THEN 1 END) / NULLIF(COUNT(*), 0), 1) as verified_percentage,
    MIN(receipt_reviewed_at) as first_review_date,
    MAX(receipt_reviewed_at) as last_review_date
FROM receipts
WHERE exclude_from_reports = FALSE OR exclude_from_reports IS NULL;

-- Create view for problematic receipts
CREATE OR REPLACE VIEW receipts_needing_attention AS
SELECT 
    receipt_id,
    receipt_date,
    vendor_name,
    gross_amount,
    category,
    banking_transaction_id,
    receipt_review_status,
    receipt_review_notes,
    receipt_reviewed_at,
    receipt_reviewed_by
FROM receipts
WHERE receipt_review_status IN ('missing', 'unreadable', 'data-error')
ORDER BY receipt_date DESC;

-- Grant permissions
GRANT SELECT ON receipt_review_summary TO PUBLIC;
GRANT SELECT ON receipts_needing_attention TO PUBLIC;
