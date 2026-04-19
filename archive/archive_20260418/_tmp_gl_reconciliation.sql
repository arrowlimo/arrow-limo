-- 2012 GL Reconciliation to Source Data
SELECT 'Charter Revenue GL' AS line, (SELECT ROUND(SUM(credit)::numeric, 2) FROM general_ledger WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'Charter Revenue')::text AS amount
UNION ALL
SELECT 'Income Ledger 2012', (SELECT ROUND(SUM(gross_amount)::numeric, 2) FROM income_ledger WHERE EXTRACT(YEAR FROM transaction_date) = 2012)::text
UNION ALL
SELECT 'A/R Payments GL', (SELECT ROUND(SUM(credit)::numeric, 2) FROM general_ledger WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'Accounts Receivable')::text
UNION ALL
SELECT 'Charter Payments source', (SELECT ROUND(SUM(amount)::numeric, 2) FROM charter_payments cp JOIN charters c ON c.reserve_number = cp.charter_id WHERE EXTRACT(YEAR FROM c.charter_date) = 2012)::text
UNION ALL
SELECT 'Banking Cash GL Balance', (SELECT ROUND((SUM(debit) - SUM(credit))::numeric, 2) FROM general_ledger WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'Cash/Bank')::text
UNION ALL
SELECT 'Banking Tx Net', (SELECT ROUND((SUM(COALESCE(debit_amount, 0)) - SUM(COALESCE(credit_amount, 0)))::numeric, 2) FROM banking_transactions WHERE EXTRACT(YEAR FROM transaction_date) = 2012)::text
UNION ALL
SELECT 'Total Expenses GL', (SELECT ROUND(SUM(debit)::numeric, 2) FROM general_ledger WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name LIKE 'Expenses - %')::text
UNION ALL
SELECT 'Total Receipts', (SELECT ROUND(SUM(gross_amount)::numeric, 2) FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2012)::text;
