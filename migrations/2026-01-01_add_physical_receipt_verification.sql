-- Add physical receipt verification columns to receipts table
-- Matched receipts (linked to banking_transaction_id) are considered physically verified

-- Add columns if they don't exist
ALTER TABLE receipts
ADD COLUMN IF NOT EXISTS is_paper_verified BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS paper_verification_date TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS verified_by_user VARCHAR(255) DEFAULT NULL;

-- Auto-populate: Any receipt linked to banking is considered paper-verified
UPDATE receipts
SET 
  is_paper_verified = TRUE,
  paper_verification_date = COALESCE(paper_verification_date, created_at)
WHERE banking_transaction_id IS NOT NULL 
  AND is_paper_verified = FALSE;

-- Create index for quick lookup of verified receipts
CREATE INDEX IF NOT EXISTS idx_receipts_paper_verified 
ON receipts(is_paper_verified, paper_verification_date);

-- Create view: Summary of verification status
DROP VIEW IF EXISTS receipt_verification_summary;
CREATE VIEW receipt_verification_summary AS
SELECT 
  COUNT(*) as total_receipts,
  SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) as physically_verified_count,
  SUM(CASE WHEN NOT is_paper_verified THEN 1 ELSE 0 END) as unverified_count,
  ROUND(100.0 * SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(*), 0), 1) as verification_percentage,
  MIN(receipt_date) as earliest_receipt_date,
  MAX(receipt_date) as latest_receipt_date
FROM receipts
WHERE business_personal != 'personal' 
  AND is_personal_purchase = FALSE;

-- Create view: Verified receipts with details
DROP VIEW IF EXISTS verified_receipts_detail;
CREATE VIEW verified_receipts_detail AS
SELECT 
  r.receipt_id,
  r.receipt_date,
  r.vendor_name,
  r.gross_amount,
  r.category,
  r.is_paper_verified,
  r.paper_verification_date,
  bt.transaction_id as banking_id,
  bt.transaction_date as banking_date,
  bt.description as banking_description,
  bt.debit_amount as banking_amount
FROM receipts r
LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
WHERE r.is_paper_verified = TRUE
ORDER BY r.receipt_date DESC;

-- Comment on columns
COMMENT ON COLUMN receipts.is_paper_verified IS 'Paper receipt physically verified (matched to banking transaction)';
COMMENT ON COLUMN receipts.paper_verification_date IS 'Date when paper receipt was verified';
COMMENT ON COLUMN receipts.verified_by_user IS 'User who verified the physical receipt';
