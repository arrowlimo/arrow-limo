-- Apply corporate linking structure to resolve multi-user accounts

-- For each account_number with multiple clients, set the first as corporate_parent
UPDATE clients c1 SET 
  account_type = 'corporate_parent',
  parent_client_id = NULL
WHERE client_id IN (
  SELECT MIN(client_id) FROM clients 
  GROUP BY account_number 
  HAVING COUNT(*) > 1
);

-- Set remaining duplicates as corporate_child pointing to parent
UPDATE clients c2 SET
  account_type = 'corporate_child',
  parent_client_id = (
    SELECT client_id FROM clients c1
    WHERE c1.account_number = c2.account_number
    AND c1.account_type = 'corporate_parent'
    LIMIT 1
  )
WHERE account_number IN (
  SELECT account_number FROM clients 
  GROUP BY account_number 
  HAVING COUNT(*) > 1
) AND account_type = 'individual';

-- Verify results
SELECT 
  account_type, 
  COUNT(*) as count
FROM clients 
WHERE account_type IN ('corporate_parent', 'corporate_child')
GROUP BY account_type;

-- Show example: Account 01007 structure
SELECT 
  client_id,
  account_number, 
  company_name,
  client_name,
  account_type,
  parent_client_id
FROM clients 
WHERE account_number IN ('01007', '01008', '01024', '00001')
ORDER BY account_number, client_id;
