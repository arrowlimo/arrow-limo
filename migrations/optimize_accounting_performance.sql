-- Optimize Accounting Page Performance
-- Addresses slow load times for /accounting page

-- 1. Add partial indexes for receipt verification queries
CREATE INDEX IF NOT EXISTS idx_receipts_verification_business 
ON receipts(is_paper_verified, receipt_date DESC)
WHERE business_personal != 'personal' AND is_personal_purchase = FALSE;

CREATE INDEX IF NOT EXISTS idx_receipts_paper_verified_true
ON receipts(receipt_date DESC)
WHERE is_paper_verified = TRUE;

CREATE INDEX IF NOT EXISTS idx_receipts_paper_verified_false
ON receipts(receipt_date DESC)
WHERE is_paper_verified = FALSE;

-- 2. Add composite index for charter date filtering (month/year queries)
-- Replace EXTRACT queries with date range queries for better performance
CREATE INDEX IF NOT EXISTS idx_charters_date_year_month
ON charters(EXTRACT(YEAR FROM charter_date), EXTRACT(MONTH FROM charter_date), charter_date);

-- 3. Create materialized view for receipt verification summary (refresh periodically)
DROP MATERIALIZED VIEW IF EXISTS mv_receipt_verification_summary CASCADE;
CREATE MATERIALIZED VIEW mv_receipt_verification_summary AS
SELECT
  1 AS id,  -- Add a constant ID for unique index
  COUNT(*) AS total_receipts,
  SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) AS physically_verified_count,
  SUM(CASE WHEN NOT is_paper_verified THEN 1 ELSE 0 END) AS unverified_count,
  ROUND(100.0 * SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(*), 0), 2) AS verification_percentage
FROM receipts
WHERE business_personal != 'personal'
  AND is_personal_purchase = FALSE;

-- Create unique index to allow concurrent refresh
CREATE UNIQUE INDEX idx_mv_receipt_verification_summary_id ON mv_receipt_verification_summary (id);

-- 4. Create materialized view for year breakdown (refresh periodically)
DROP MATERIALIZED VIEW IF EXISTS mv_receipt_verification_by_year CASCADE;
CREATE MATERIALIZED VIEW mv_receipt_verification_by_year AS
SELECT
  EXTRACT(YEAR FROM receipt_date)::INT as year,
  COUNT(*) as total,
  SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) as verified,
  ROUND(100.0 * SUM(CASE WHEN is_paper_verified THEN 1 ELSE 0 END) /
        NULLIF(COUNT(*), 0), 1) as percentage
FROM receipts
WHERE business_personal != 'personal'
  AND is_personal_purchase = FALSE
GROUP BY EXTRACT(YEAR FROM receipt_date)
ORDER BY year;

CREATE UNIQUE INDEX idx_mv_receipt_verification_by_year_year ON mv_receipt_verification_by_year (year);

-- 5. Add index for receipts by category (for expense summary)
CREATE INDEX IF NOT EXISTS idx_receipts_category_date
ON receipts(category, receipt_date DESC)
WHERE category IS NOT NULL;

-- 6. Add index for GL account filtering
CREATE INDEX IF NOT EXISTS idx_receipts_gl_account
ON receipts(gl_account_code, receipt_date DESC)
WHERE gl_account_code IS NOT NULL;

-- Refresh materialized views
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_receipt_verification_summary;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_receipt_verification_by_year;

-- Grant permissions
GRANT SELECT ON mv_receipt_verification_summary TO PUBLIC;
GRANT SELECT ON mv_receipt_verification_by_year TO PUBLIC;

-- NOTES:
-- These materialized views should be refreshed periodically (e.g., nightly or hourly)
-- Add to cron/scheduler:
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_receipt_verification_summary;
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_receipt_verification_by_year;
