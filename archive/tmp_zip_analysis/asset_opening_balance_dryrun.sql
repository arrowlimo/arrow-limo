-- Read-only dry-run journal simulation for missing CRA asset balances in ALMS
-- No INSERT/UPDATE/DELETE statements
WITH missing_assets(code, account_name, amount) AS (
  VALUES
    ('1700', '', 665257.82),
    ('1701', '', -307004.33)
), simulated_lines AS (
  SELECT code, account_name, 'ASSET'::text AS line_type,
         CASE WHEN amount >= 0 THEN amount ELSE 0 END AS debit,
         CASE WHEN amount < 0 THEN -amount ELSE 0 END AS credit
  FROM missing_assets
  UNION ALL
  SELECT 'EQUITY_OPENING_BALANCE' AS code, 'Balancing equity placeholder' AS account_name, 'EQUITY'::text AS line_type,
         CASE WHEN SUM(amount) < 0 THEN -SUM(amount) ELSE 0 END AS debit,
         CASE WHEN SUM(amount) >= 0 THEN SUM(amount) ELSE 0 END AS credit
  FROM missing_assets
)
SELECT code, account_name, line_type, ROUND(debit::numeric,2) AS debit, ROUND(credit::numeric,2) AS credit
FROM simulated_lines
ORDER BY CASE WHEN line_type = 'ASSET' THEN 1 ELSE 2 END, code;
