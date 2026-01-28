-- Add automatic verification tracking for receipt edits
-- Purpose: Track which receipts have been manually reviewed and edited during audit

-- Add verification tracking columns
ALTER TABLE receipts
ADD COLUMN IF NOT EXISTS verified_by_edit BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP DEFAULT NULL,
ADD COLUMN IF NOT EXISTS verified_by_user VARCHAR(255) DEFAULT NULL;

-- Create index for quick lookup of verified receipts
CREATE INDEX IF NOT EXISTS idx_receipts_verified_by_edit 
ON receipts(verified_by_edit, verified_at);

-- Add comment explaining the column
COMMENT ON COLUMN receipts.verified_by_edit IS 'Auto-set to TRUE when receipt is manually edited, indicating it has been reviewed during audit';
COMMENT ON COLUMN receipts.verified_at IS 'Timestamp when receipt was last edited/verified';
COMMENT ON COLUMN receipts.verified_by_user IS 'Username or system that performed the verification';

-- Create verification summary view
DROP VIEW IF EXISTS receipt_verification_audit_summary CASCADE;
CREATE VIEW receipt_verification_audit_summary AS
SELECT 
  COUNT(*) as total_receipts,
  SUM(CASE WHEN verified_by_edit THEN 1 ELSE 0 END) as verified_count,
  SUM(CASE WHEN NOT verified_by_edit OR verified_by_edit IS NULL THEN 1 ELSE 0 END) as unverified_count,
  ROUND(100.0 * SUM(CASE WHEN verified_by_edit THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(*), 0), 1) as verification_percentage,
  MIN(verified_at) as first_verification_date,
  MAX(verified_at) as last_verification_date,
  COUNT(DISTINCT verified_by_user) as unique_verifiers
FROM receipts
WHERE business_personal != 'personal' 
  OR business_personal IS NULL;

-- Create detailed verified receipts view
DROP VIEW IF EXISTS verified_receipts_audit_detail CASCADE;
CREATE VIEW verified_receipts_audit_detail AS
SELECT 
  r.receipt_id,
  r.receipt_date,
  r.vendor_name,
  r.gross_amount,
  r.category,
  r.gl_account_code,
  r.verified_by_edit,
  r.verified_at,
  r.verified_by_user,
  r.updated_at,
  r.created_at,
  CASE 
    WHEN r.verified_by_edit THEN 'Manually Verified'
    WHEN r.banking_transaction_id IS NOT NULL THEN 'Banking Linked'
    ELSE 'Unverified'
  END as verification_status
FROM receipts r
WHERE r.business_personal != 'personal' OR r.business_personal IS NULL
ORDER BY r.verified_at DESC NULLS LAST, r.receipt_date DESC;

-- Show summary
SELECT * FROM receipt_verification_audit_summary;
