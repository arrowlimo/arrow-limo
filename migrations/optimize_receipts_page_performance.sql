-- Optimize Receipts Page Load Performance

-- 1. Add index for vendor_name to speed up DISTINCT query
CREATE INDEX IF NOT EXISTS idx_receipts_vendor_name ON receipts(vendor_name);

-- 2. Create materialized view for vendor list (refresh periodically)
DROP MATERIALIZED VIEW IF EXISTS mv_vendor_list CASCADE;
CREATE MATERIALIZED VIEW mv_vendor_list AS
SELECT 
    vendor_name as name, 
    -- Use the most common canonical_vendor for each vendor_name
    (SELECT canonical_vendor 
     FROM receipts r2 
     WHERE r2.vendor_name = r1.vendor_name 
     GROUP BY canonical_vendor 
     ORDER BY COUNT(*) DESC 
     LIMIT 1) as canonical
FROM (
    SELECT DISTINCT vendor_name
    FROM receipts
    WHERE vendor_name IS NOT NULL
      AND vendor_name != ''
      AND vendor_name != 'BANKING TRANSACTION'
) r1
ORDER BY name;

-- Create unique index on name for concurrent refresh
CREATE UNIQUE INDEX idx_mv_vendor_list_name ON mv_vendor_list (name);

-- 3. Add index for canonical_vendor
CREATE INDEX IF NOT EXISTS idx_receipts_canonical_vendor ON receipts(canonical_vendor);

-- Initial refresh
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_vendor_list;

-- Grant permissions
GRANT SELECT ON mv_vendor_list TO PUBLIC;
