-- PHASE 1: DATA QUALITY FIXES
-- Generated: 2026-01-23 based on comprehensive audit findings
-- Purpose: Fix data quality issues found in Phase 1 audit

-- =============================================================================
-- BACKUP BEFORE CHANGES
-- =============================================================================
-- pg_dump -h localhost -U postgres -d almsdata -F c -f almsdata_backup_BEFORE_PHASE1_FIXES_20260123.dump

BEGIN;

-- =============================================================================
-- FIX 1: CLIENTS TABLE SCHEMA ALIGNMENT
-- =============================================================================
-- Problem: Code expects 'name', 'phone', 'address' but DB has 'company_name', 'primary_phone', 'address_line1'
-- Solution: Add new columns and migrate data

-- Add new standardized columns to clients table
ALTER TABLE clients ADD COLUMN IF NOT EXISTS name VARCHAR;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS phone VARCHAR;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS notes TEXT;

-- Migrate data from old columns to new columns
UPDATE clients 
SET 
    name = COALESCE(company_name, client_name),
    phone = primary_phone,
    address = address_line1,
    notes = contact_info
WHERE name IS NULL;

-- Create index on new name column for performance
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);

-- =============================================================================
-- FIX 2: CLEAN PHONE NUMBER DATA
-- =============================================================================
-- Problem: Phone columns contain partial numbers like "403" instead of full phone numbers
-- Solution: Mark incomplete phone numbers as NULL for data cleanup

-- Clean clients phone numbers
UPDATE clients 
SET phone = NULL 
WHERE phone IS NOT NULL 
  AND LENGTH(REGEXP_REPLACE(phone, '[^0-9]', '', 'g')) < 10;

UPDATE clients 
SET primary_phone = NULL 
WHERE primary_phone IS NOT NULL 
  AND LENGTH(REGEXP_REPLACE(primary_phone, '[^0-9]', '', 'g')) < 10;

-- Clean employees phone numbers
UPDATE employees 
SET phone = NULL 
WHERE phone IS NOT NULL 
  AND LENGTH(REGEXP_REPLACE(phone, '[^0-9]', '', 'g')) < 10;

UPDATE employees 
SET cell_phone = NULL 
WHERE cell_phone IS NOT NULL 
  AND LENGTH(REGEXP_REPLACE(cell_phone, '[^0-9]', '', 'g')) < 10;

-- =============================================================================
-- FIX 3: CLEAN EMAIL DATA IN EMAIL_FINANCIAL_EVENTS
-- =============================================================================
-- Problem: from_email contains "Name <email>" instead of just "email"
-- Solution: Extract email from angle brackets

UPDATE email_financial_events
SET from_email = SUBSTRING(from_email FROM '<(.+)>')
WHERE from_email LIKE '%<%>%'
  AND from_email ~ '<[^>]+@[^>]+>';

-- =============================================================================
-- FIX 4: CLEAN MISPLACED DATA IN LIMO_CLIENTS
-- =============================================================================
-- Problem: Email column contains postal codes, phone columns contain dates
-- These are legacy import errors from LMS system

-- Mark invalid emails as NULL (postal codes in email field)
UPDATE limo_clients
SET email = NULL
WHERE email IS NOT NULL
  AND email ~ '^[A-Z][0-9][A-Z]\s?[0-9][A-Z][0-9]$';  -- Canadian postal code pattern

-- Mark invalid phone numbers as NULL (dates in phone fields)
UPDATE limo_clients
SET work_phone = NULL
WHERE work_phone ~ '^\d{1,2}/\d{1,2}/\d{4}$';  -- Date pattern

UPDATE limo_clients
SET fax_phone = NULL
WHERE fax_phone ~ '^\d{1,2}/\d{1,2}/\d{4}$';

-- Also clean in limo_clients_clean
UPDATE limo_clients_clean
SET email = NULL
WHERE email IS NOT NULL
  AND email ~ '^[A-Z][0-9][A-Z]\s?[0-9][A-Z][0-9]$';

UPDATE limo_clients_clean
SET work_phone = NULL
WHERE work_phone ~ '^\d{1,2}/\d{1,2}/\d{4}$';

UPDATE limo_clients_clean
SET fax_phone = NULL
WHERE fax_phone ~ '^\d{1,2}/\d{1,2}/\d{4}$';

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================

-- Verify clients table migration
SELECT 
    COUNT(*) as total_clients,
    COUNT(name) as have_name,
    COUNT(phone) as have_phone,
    COUNT(company_name) as have_company_name,
    COUNT(primary_phone) as have_primary_phone
FROM clients;

-- Verify phone cleanup
SELECT 
    'clients' as table_name,
    COUNT(*) FILTER (WHERE LENGTH(REGEXP_REPLACE(phone, '[^0-9]', '', 'g')) < 10) as short_phones
FROM clients
WHERE phone IS NOT NULL
UNION ALL
SELECT 
    'employees',
    COUNT(*) FILTER (WHERE LENGTH(REGEXP_REPLACE(phone, '[^0-9]', '', 'g')) < 10)
FROM employees
WHERE phone IS NOT NULL;

-- Verify email cleanup
SELECT 
    COUNT(*) as emails_with_angle_brackets
FROM email_financial_events
WHERE from_email LIKE '%<%>%';

COMMIT;

-- =============================================================================
-- POST-FIX NOTES
-- =============================================================================
-- After running this migration:
-- 1. Update all Python code to use 'name', 'phone', 'address' columns
-- 2. Re-run Phase 1 audit to verify fixes
-- 3. Consider deprecating old columns (company_name, primary_phone, address_line1) after code migration
-- 4. Update DATABASE_SCHEMA_REFERENCE.md
