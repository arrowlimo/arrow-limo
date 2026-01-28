-- CLIENTS TABLE: NAME STANDARDIZATION
-- Purpose: Separate individual names (Last, First) from company names
-- - Individual names in "Last, First" format → split into last_name/first_name; company_name = "None"
-- - Actual company names (no comma) → stay in company_name; first_name/last_name empty
-- Generated: 2026-01-24

BEGIN;

-- =============================================================================
-- STEP 1: ADD COLUMNS IF MISSING
-- =============================================================================
ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS first_name VARCHAR,
  ADD COLUMN IF NOT EXISTS last_name VARCHAR;

-- =============================================================================
-- STEP 2: PREVIEW (dry-run) - Check affected rows
-- =============================================================================
-- Run this first to see what will change:
/*
SELECT COUNT(*) as individual_names_with_comma
FROM clients
WHERE company_name LIKE '%,%'
  AND (last_name IS NULL AND first_name IS NULL);
*/

-- =============================================================================
-- STEP 3: SPLIT COMMA-SEPARATED NAMES (ONLY if first/last are empty)
-- =============================================================================
-- For names like "Smith, John" → last_name='Smith', first_name='John', company_name='None'
-- ONLY process if first_name AND last_name are BOTH NULL (don't overwrite existing individual names)
-- Multi-word companies without commas (e.g., "Red Deer Lodge") are left untouched
UPDATE clients
SET 
  last_name = NULLIF(trim(split_part(company_name, ',', 1)), ''),
  first_name = NULLIF(trim(split_part(company_name, ',', 2)), ''),
  company_name = 'None'
WHERE company_name LIKE '%,%'
  AND last_name IS NULL
  AND first_name IS NULL;

-- =============================================================================
-- STEP 4: VERIFICATION QUERIES
-- =============================================================================

-- Count individual vs company clients
SELECT 
  COUNT(*) FILTER (WHERE company_name = 'None') as individual_clients,
  COUNT(*) FILTER (WHERE company_name != 'None') as company_clients,
  COUNT(*) as total_clients
FROM clients;

-- Show sample of processed individuals
SELECT 
  client_id,
  last_name,
  first_name,
  company_name,
  account_number
FROM clients
WHERE company_name = 'None'
LIMIT 10;

-- Show sample of company names
SELECT 
  client_id,
  company_name,
  last_name,
  first_name,
  account_number
FROM clients
WHERE company_name != 'None'
LIMIT 10;

-- Check for any remaining mixed data (comma in company_name but not processed)
SELECT 
  client_id,
  company_name,
  last_name,
  first_name
FROM clients
WHERE company_name LIKE '%,%'
  AND company_name != 'None'
LIMIT 5;

COMMIT;

-- =============================================================================
-- POST-EXECUTION NOTES
-- =============================================================================
-- 1. Individual clients now identified by company_name = 'None'
-- 2. Names split: "Smith, John" → last_name='Smith', first_name='John'
-- 3. Actual companies preserved in company_name
-- 4. Update client_drill_down.py UI to display:
--    - For individuals: "John Smith" (concat first_name + last_name)
--    - For companies: company_name as-is
-- 5. Add search index for name lookups (optional):
--    CREATE INDEX IF NOT EXISTS idx_clients_name_search
--      ON clients (lower(company_name), lower(last_name), lower(first_name));
