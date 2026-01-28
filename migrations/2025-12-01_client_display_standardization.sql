-- Standardize client display naming and backfill charters.client_display_name
-- Uses COALESCE(client_name, company_name) as the canonical display string.

-- Backfill existing charters display from clients
UPDATE charters c
SET client_display_name = COALESCE(cl.client_name, cl.company_name)
FROM clients cl
WHERE c.client_id = cl.client_id
  AND (c.client_display_name IS NULL OR TRIM(c.client_display_name) = ''
       OR c.client_display_name <> COALESCE(cl.client_name, cl.company_name));

-- Optional: create a helper view for consistent client display usage
CREATE OR REPLACE VIEW v_clients_display AS
SELECT 
  client_id,
  client_name,
  company_name,
  COALESCE(client_name, company_name) AS display_name,
  account_number,
  email,
  phone_number,
  created_at,
  updated_at
FROM clients;
