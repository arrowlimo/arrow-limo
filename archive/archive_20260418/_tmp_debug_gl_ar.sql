-- Debug: What actually got posted to GL vs what's in charter_payments
SELECT 'charter_payments for 2012' AS check_item, COUNT(*)::text AS count_val, ROUND(SUM(amount)::numeric, 2)::text AS total FROM charter_payments cp
JOIN charters c ON c.reserve_number = cp.charter_id WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
UNION ALL
SELECT 'GL A/R credits for 2012', COUNT(*)::text, ROUND(SUM(credit)::numeric, 2)::text FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 AND account_name = 'Accounts Receivable'
UNION ALL
SELECT 'GL charter_payments source', COUNT(*)::text, ROUND(SUM(credit)::numeric, 2)::text FROM general_ledger
WHERE EXTRACT(YEAR FROM date) = 2012 AND source = 'charter_payments';
