-- CLIENTS TABLE: CORPORATE HIERARCHY
-- Purpose: Link employees to their parent company
-- - corporate_parent_id = 0 → Individual booking
-- - corporate_parent_id > 0 → Employee of that company
-- - corporate_role → Position within company structure (primary, employee_1, employee_2, etc.)
-- Generated: 2026-01-24

BEGIN;

-- =============================================================================
-- STEP 1: ADD COLUMNS
-- =============================================================================
ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS corporate_parent_id INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS corporate_role VARCHAR DEFAULT NULL;

-- =============================================================================
-- STEP 2: ADD FOREIGN KEY CONSTRAINT
-- =============================================================================
-- Note: We use 0 as a sentinel value for "no parent" (individual clients)
-- So we DON'T add an FK constraint to enforce referential integrity
-- (0 is not a valid client_id, it's just a flag)
-- Integrity must be maintained in the application layer

-- =============================================================================
-- STEP 3: CREATE INDEX FOR FAST LOOKUPS
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_clients_corporate_parent_id
  ON clients(corporate_parent_id);

CREATE INDEX IF NOT EXISTS idx_clients_corporate_role
  ON clients(corporate_role);

CREATE INDEX IF NOT EXISTS idx_clients_corporate_hierarchy
  ON clients(corporate_parent_id, corporate_role);

-- =============================================================================
-- STEP 4: VERIFICATION QUERIES
-- =============================================================================

-- Count individuals vs corporate clients
SELECT 
  COUNT(*) FILTER (WHERE corporate_parent_id = 0) as individual_clients,
  COUNT(*) FILTER (WHERE corporate_parent_id > 0) as corporate_employee_clients,
  COUNT(*) as total_clients
FROM clients;

-- Show example corporate hierarchies
SELECT 
  parent.client_id as company_id,
  parent.client_name as company_name,
  parent.company_name,
  COUNT(*) FILTER (WHERE child.corporate_role = 'primary') as primary_contacts,
  COUNT(*) FILTER (WHERE child.corporate_role LIKE 'employee_%') as employee_slots,
  COUNT(*) as total_members
FROM clients parent
LEFT JOIN clients child ON child.corporate_parent_id = parent.client_id
WHERE parent.corporate_parent_id = 0
GROUP BY parent.client_id, parent.client_name, parent.company_name
HAVING COUNT(*) > 1
LIMIT 20;

-- Show sample corporate structure
SELECT 
  client_id,
  client_name,
  company_name,
  corporate_parent_id,
  corporate_role
FROM clients
WHERE corporate_parent_id > 0
LIMIT 10;

COMMIT;

-- =============================================================================
-- POST-EXECUTION NOTES
-- =============================================================================
-- 1. All clients default to corporate_parent_id = 0 (individual)
-- 2. To link an employee to a company:
--    UPDATE clients SET corporate_parent_id = 1, corporate_role = 'primary'
--    WHERE client_id = 2;
--
-- 3. To add more employees:
--    UPDATE clients SET corporate_parent_id = 1, corporate_role = 'employee_1'
--    WHERE client_id = 3;
--    UPDATE clients SET corporate_parent_id = 1, corporate_role = 'employee_2'
--    WHERE client_id = 4;
--
-- 4. Query examples:
--    -- Find all individuals
--    SELECT * FROM clients WHERE corporate_parent_id = 0;
--
--    -- Find all employees of company (client_id=1)
--    SELECT * FROM clients WHERE corporate_parent_id = 1;
--
--    -- Find primary contact for company
--    SELECT * FROM clients WHERE corporate_parent_id = 1 AND corporate_role = 'primary';
--
-- 5. Update DATABASE_SCHEMA_REFERENCE.md after confirming success
